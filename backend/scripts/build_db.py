"""
Builds backend/data/grn.sqlite3 from local data files committed to the repo.

Human data: TRRUST v2 TSV + gene_names.json (from mygene.info)
Arabidopsis data: PlantRegMap filtered TSV + gene_names_arabidopsis.json
ATRM direction labels: atrm_regulations.tsv (activation/repression for 1,431 literature-curated pairs)

No network access needed. Safe to re-run; always rebuilds from scratch.
"""
import gzip
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

# Human (TRRUST v2)
TRRUST_TSV = DATA_DIR / "trrust_rawdata.human.tsv"
HUMAN_NAMES_JSON = DATA_DIR / "gene_names.json"

# Arabidopsis (PlantRegMap, filtered to literature + ChIP-seq + FunTFBS)
ARABIDOPSIS_TSV = DATA_DIR / "regulation_arabidopsis.tsv"
ARABIDOPSIS_NAMES_JSON = DATA_DIR / "gene_names_arabidopsis.json"

# Tomato (PlantRegMap FunTFBS; see fetch_tomato_regulation.py). Optional.
TOMATO_TSV = DATA_DIR / "regulation_tomato.tsv"
# Arabidopsis->plant ortholog map for projecting the network onto tomato/petunia.
ORTHOLOG_MAP_JSON = DATA_DIR / "ortholog_map_plaza.json"
INFERRED_CONF_FACTOR = 0.7   # confidence penalty for orthology-projected edges

# ATRM direction labels (literature-curated activation/repression)
ATRM_TSV = DATA_DIR / "atrm_regulations.tsv"

# Genome coordinates + cross-species orthologs.
# OMA (animal side + Arabidopsis bridge): fetch_genome_data.py
# PLAZA (plant side: Arabidopsis/tomato/petunia): fetch_plaza_data.py
POSITIONS_JSON = DATA_DIR / "genome_positions.json"
ORTHOLOGS_JSON = DATA_DIR / "orthologs.json"
GENES_JSON = DATA_DIR / "genome_genes.json"
PLAZA_POSITIONS_JSON = DATA_DIR / "plaza_positions.json"
PLAZA_ORTHOLOGS_JSON = DATA_DIR / "orthologs_plaza.json"
PLAZA_GENES_JSON = DATA_DIR / "genome_genes_plaza.json"
PLAZA_SYMBOLS_JSON = DATA_DIR / "gene_symbols_plaza.json"
GO_JSON = DATA_DIR / "go_annotations.json.gz"
# BLAST-curated gene identities (e.g. petunia AN2/AN1/AN11 …); see blast_regulators.py
REGULATOR_MAP_JSON = DATA_DIR / "regulator_map.json"

# Sequence-context ingestion bundle (Path B; optional — see the tomato SL4.0
# ingestion plan). Each is a list of row-dicts; absent files leave the tables
# empty. Keys mirror the table columns.
# Each entry: (basename, columns). The loader reads <name>.json.gz or <name>.json.
SEQCTX_FILES = {
    "gene_id_crosswalk": (
        "gene_id_crosswalk",
        ["species", "atlas_gene_id", "ext_gene_id", "ext_assembly", "relation"],
    ),
    "gene_windows": (
        "gene_windows",
        ["ext_gene_id", "assembly", "window_type", "chromosome", "start", "end", "strand"],
    ),
    "motifs": (
        "motifs",
        ["motif_id", "source", "jaspar_id", "tf_gene_id", "tf_symbol"],
    ),
    "motif_hits": (
        "motif_hits",
        ["ext_gene_id", "motif_id", "assembly", "window_type", "chromosome",
         "start", "end", "strand", "score", "p_value", "tier", "site_confidence"],
    ),
    "pathways": (
        "pathways",
        ["pathway_id", "name", "source"],
    ),
    "pathway_annotations": (
        "pathway_annotations",
        ["gene_id", "pathway_id"],
    ),
    "trait_associations": (
        "trait_associations",
        ["gene_id", "trait", "pubmed_id"],
    ),
}


def load_rows(basename):
    """Read + concatenate list-of-dicts caches for a sequence-context table across
    all species: <basename>.json[.gz] and <basename>_<species>.json[.gz]."""
    import gzip
    rows = []
    seen = set()
    for path in sorted(DATA_DIR.glob(f"{basename}*.json*")):
        if path.name in seen or path.suffix not in (".gz", ".json"):
            continue
        # avoid loading both foo.json and foo.json.gz for the same stem
        stem = path.name[:-3] if path.name.endswith(".gz") else path.name
        if stem in seen:
            continue
        seen.add(stem)
        if path.name.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                rows.extend(json.load(f))
        else:
            rows.extend(json.loads(path.read_text()))
    return rows

# Authoritative assembly chromosome lengths (bp) for scaled ideograms.
# Human: GRCh38; Arabidopsis: TAIR10. Falls back to max observed coordinate
# for species/chromosomes not listed here.
CHROMOSOME_LENGTHS = {
    "human": {
        "1": 248956422, "2": 242193529, "3": 198295559, "4": 190214555,
        "5": 181538259, "6": 170805979, "7": 159345973, "8": 145138636,
        "9": 138394717, "10": 133797422, "11": 135086622, "12": 133275309,
        "13": 114364328, "14": 107043718, "15": 101991189, "16": 90338345,
        "17": 83257441, "18": 80373285, "19": 58617616, "20": 64444167,
        "21": 46709983, "22": 50818468, "X": 156040895, "Y": 57227415,
    },
    "arabidopsis": {
        "1": 30427671, "2": 19698289, "3": 23459830, "4": 18585056, "5": 26975502,
    },
    "mouse": {  # GRCm39
        "1": 195154279, "2": 181755017, "3": 159745316, "4": 156860686,
        "5": 151758149, "6": 149588044, "7": 144995196, "8": 130127694,
        "9": 124359700, "10": 130530862, "11": 121973369, "12": 120092757,
        "13": 120883175, "14": 125139656, "15": 104073951, "16": 98008968,
        "17": 95294699, "18": 90720763, "19": 61420004, "X": 169476592, "Y": 91455967,
    },
    "tomato": {  # SL2.50 (chromosome names normalized to bare numbers)
        "0": 21805821, "1": 98543444, "2": 55340444, "3": 70787664,
        "4": 66470942, "5": 65875088, "6": 49751636, "7": 68045021,
        "8": 65866657, "9": 72482091, "10": 65527505, "11": 56302525, "12": 67145203,
    },
}


def norm_chrom(species, name):
    """Normalize chromosome names to a canonical short form so different sources
    and assemblies agree: OMA calls Arabidopsis chr 1 "1" but PLAZA calls it
    "Chr1"; tomato's SL2.50 GFF names it "SL2.50ch01". Reduce both to "1"."""
    name = str(name)
    if species == "tomato":
        m = re.search(r"ch0*(\d+)$", name)
        if m:
            return m.group(1)
    return re.sub(r"^chr", "", name, flags=re.IGNORECASE)


def load_human_edges():
    """Parse TRRUST, merging duplicate (tf, target) pairs across papers."""
    if not TRRUST_TSV.exists():
        print(f"  (skip) {TRRUST_TSV.name} not fetched — human network empty")
        return []
    pair_data = defaultdict(lambda: {"Activation": set(), "Repression": set()})
    with open(TRRUST_TSV) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 4:
                continue
            tf, target, reg, pmids = parts
            if reg not in ("Activation", "Repression"):
                continue
            pair_data[(tf, target)][reg] |= set(pmids.split(";"))

    edges = []
    for (tf, target), d in pair_data.items():
        n_act, n_rep = len(d["Activation"]), len(d["Repression"])
        reg = "activation" if n_act >= n_rep else "repression"
        all_pmids = d["Activation"] | d["Repression"]
        confidence = round(min(0.5 + 0.1 * len(all_pmids), 0.95), 2)
        pmids = sorted(p for p in all_pmids if p.isdigit())
        edges.append((tf, target, reg, confidence, "TRRUST", pmids))
    return edges


def load_atrm_directions():
    """Load ATRM literature-curated direction labels (A/R/D)."""
    directions = {}
    if not ATRM_TSV.exists():
        return directions
    with open(ATRM_TSV) as f:
        next(f)  # skip header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            tf, target, label = parts[0], parts[1], parts[4]
            if label == "A":
                directions[(tf, target)] = "activation"
            elif label == "R":
                directions[(tf, target)] = "repression"
            elif label == "D":
                directions[(tf, target)] = "activation"
    return directions


def load_arabidopsis_edges():
    """Parse filtered PlantRegMap TSV, overlaying ATRM direction labels."""
    atrm = load_atrm_directions()
    edges = []
    seen = set()
    directed = 0
    if not ARABIDOPSIS_TSV.exists():
        print(f"  (skip) {ARABIDOPSIS_TSV.name} not fetched — arabidopsis network empty")
        return edges
    with open(ARABIDOPSIS_TSV) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            tf, target, reg, confidence = parts[0], parts[1], parts[2], float(parts[3])
            key = (tf, target)
            if key in seen:
                continue
            seen.add(key)
            if key in atrm:
                reg = atrm[key]
                confidence = max(confidence, 0.90)
                directed += 1
            edges.append((tf, target, reg, confidence, "PlantRegMap", []))
    print(f"  ATRM: set direction on {directed}/{len(atrm)} literature-curated pairs")
    return edges


def load_tomato_edges():
    """Real tomato TF-target edges from PlantRegMap FunTFBS (optional file)."""
    if not TOMATO_TSV.exists():
        return []
    edges = []
    with open(TOMATO_TSV) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            tf, target, reg, conf = parts[0], parts[1], parts[2], float(parts[3])
            edges.append((tf, target, reg, conf, "PlantRegMap", []))
    return edges


def build():
    # Load edges
    human_edges = load_human_edges()
    arab_edges = load_arabidopsis_edges()
    tomato_edges = load_tomato_edges()

    # Load gene names (optional; fall back to bare ids if not fetched)
    human_names = json.loads(HUMAN_NAMES_JSON.read_text()) if HUMAN_NAMES_JSON.exists() else {}
    arab_names = json.loads(ARABIDOPSIS_NAMES_JSON.read_text()) if ARABIDOPSIS_NAMES_JSON.exists() else {}

    # Human genes
    human_tfs = {tf for tf, *_ in human_edges}
    human_genes = sorted(human_tfs | {e[1] for e in human_edges})

    # Arabidopsis genes
    arab_tfs = {tf for tf, *_ in arab_edges}
    arab_all = sorted(arab_tfs | {e[1] for e in arab_edges})

    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE genes (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            species TEXT NOT NULL,
            is_tf INTEGER NOT NULL,
            gene_type TEXT,
            synonyms TEXT,         -- inferred names (e.g. Arabidopsis ortholog symbols); '; '-joined
            symbol_source TEXT     -- provenance when symbol is a curated real name (e.g. 'UniProt')
        );
        CREATE INDEX idx_genes_symbol ON genes(symbol COLLATE NOCASE);
        CREATE INDEX idx_genes_name ON genes(name COLLATE NOCASE);
        CREATE INDEX idx_genes_synonyms ON genes(synonyms COLLATE NOCASE);
        CREATE INDEX idx_genes_species ON genes(species);

        CREATE TABLE interactions (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            regulation_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            sources TEXT NOT NULL,
            pmids TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (source_id, target_id)
        );
        CREATE INDEX idx_interactions_source ON interactions(source_id);
        CREATE INDEX idx_interactions_target ON interactions(target_id);

        CREATE TABLE gene_locations (
            gene_id TEXT PRIMARY KEY,
            species TEXT NOT NULL,
            chromosome TEXT NOT NULL,
            start INTEGER NOT NULL,
            end INTEGER NOT NULL,
            strand INTEGER NOT NULL
        );
        CREATE INDEX idx_loc_species ON gene_locations(species, chromosome);

        CREATE TABLE orthologs (
            gene_a TEXT NOT NULL,
            gene_b TEXT NOT NULL,
            species_a TEXT NOT NULL,
            species_b TEXT NOT NULL,
            rel_type TEXT,
            score REAL,
            PRIMARY KEY (gene_a, gene_b)
        );
        CREATE INDEX idx_orth_species ON orthologs(species_a, species_b);
        CREATE INDEX idx_orth_a ON orthologs(gene_a);
        CREATE INDEX idx_orth_b ON orthologs(gene_b);

        CREATE TABLE chromosomes (
            species TEXT NOT NULL,
            chromosome TEXT NOT NULL,
            length INTEGER NOT NULL,
            PRIMARY KEY (species, chromosome)
        );

        CREATE TABLE go_terms (
            go_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            namespace TEXT
        );
        CREATE TABLE go_annotations (
            gene_id TEXT NOT NULL,
            go_id TEXT NOT NULL,
            PRIMARY KEY (gene_id, go_id)
        );
        CREATE INDEX idx_go_ann_gene ON go_annotations(gene_id);
        CREATE INDEX idx_go_ann_term ON go_annotations(go_id);

        -- Sequence-context layer (Path B). Populated from an external ingestion
        -- bundle (e.g. tomato SL4.0/ITAG4.1); created empty until that lands so
        -- the export endpoint's joins are always valid. Coordinates here are on
        -- the ingest assembly (BED 0-based half-open), joined to the atlas graph
        -- only through gene_id_crosswalk.
        CREATE TABLE gene_id_crosswalk (
            species       TEXT NOT NULL,
            atlas_gene_id TEXT NOT NULL,
            ext_gene_id   TEXT NOT NULL,
            ext_assembly  TEXT NOT NULL,
            relation      TEXT NOT NULL DEFAULT '1:1',
            PRIMARY KEY (atlas_gene_id, ext_gene_id)
        );
        CREATE INDEX idx_xwalk_ext ON gene_id_crosswalk(ext_gene_id);

        CREATE TABLE gene_windows (
            ext_gene_id TEXT NOT NULL,
            assembly    TEXT NOT NULL,
            window_type TEXT NOT NULL,
            chromosome  TEXT NOT NULL,
            start       INTEGER NOT NULL,
            end         INTEGER NOT NULL,
            strand      INTEGER NOT NULL,
            PRIMARY KEY (ext_gene_id, assembly, window_type, chromosome, start)
        );
        CREATE INDEX idx_gw_ext ON gene_windows(ext_gene_id);

        CREATE TABLE motifs (
            motif_id   TEXT PRIMARY KEY,
            source     TEXT NOT NULL,
            jaspar_id  TEXT,
            tf_gene_id TEXT,
            tf_symbol  TEXT
        );
        CREATE INDEX idx_motifs_tf ON motifs(tf_gene_id);

        CREATE TABLE motif_hits (
            ext_gene_id     TEXT NOT NULL,
            motif_id        TEXT NOT NULL,
            assembly        TEXT NOT NULL,
            window_type     TEXT NOT NULL,
            chromosome      TEXT NOT NULL,
            start           INTEGER NOT NULL,
            end             INTEGER NOT NULL,
            strand          INTEGER NOT NULL,
            score           REAL,
            p_value         REAL,
            tier            TEXT,
            site_confidence REAL
        );
        CREATE INDEX idx_mh_gene  ON motif_hits(ext_gene_id);
        CREATE INDEX idx_mh_motif ON motif_hits(motif_id);

        CREATE TABLE pathways (
            pathway_id TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            source     TEXT NOT NULL
        );
        CREATE TABLE pathway_annotations (
            gene_id    TEXT NOT NULL,
            pathway_id TEXT NOT NULL,
            PRIMARY KEY (gene_id, pathway_id)
        );
        CREATE INDEX idx_pathway_anno_gene ON pathway_annotations(gene_id);

        CREATE TABLE trait_associations (
            gene_id   TEXT NOT NULL,
            trait     TEXT NOT NULL,
            pubmed_id TEXT,
            source    TEXT NOT NULL DEFAULT 'GWAS Catalog',
            PRIMARY KEY (gene_id, trait)
        );
        CREATE INDEX idx_trait_gene ON trait_associations(gene_id);

        CREATE TABLE inferred_edges (
            source_id   TEXT NOT NULL,
            target_id   TEXT NOT NULL,
            method      TEXT NOT NULL DEFAULT 'GRNBoost2',
            importance  REAL NOT NULL,
            species     TEXT NOT NULL,
            PRIMARY KEY (source_id, target_id, method)
        );
        CREATE INDEX idx_ie_source ON inferred_edges(source_id);
        CREATE INDEX idx_ie_target ON inferred_edges(target_id);
        CREATE INDEX idx_ie_species ON inferred_edges(species);
    """)

    # Insert human genes
    conn.executemany(
        "INSERT INTO genes (id, symbol, name, species, is_tf, gene_type) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (sym, sym, human_names.get(sym, sym), "human", 1 if sym in human_tfs else 0, "protein_coding")
            for sym in human_genes
        ],
    )

    # Insert Arabidopsis genes (use resolved symbol if available, else locus ID)
    def arab_symbol(locus):
        entry = arab_names.get(locus)
        return entry.get("symbol", locus) if isinstance(entry, dict) else locus

    conn.executemany(
        "INSERT INTO genes (id, symbol, name, species, is_tf, gene_type) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                locus,
                arab_symbol(locus),
                arab_names.get(locus, {}).get("name", locus) if isinstance(arab_names.get(locus), dict) else locus,
                "arabidopsis",
                1 if locus in arab_tfs else 0,
                "protein_coding",
            )
            for locus in arab_all
        ],
    )
    # Real Arabidopsis symbols (excluding bare AGI ids), for inferring synonyms.
    arab_real_symbol = {
        locus: arab_symbol(locus) for locus in arab_all
        if arab_symbol(locus).upper() != locus.upper()
    }

    # Insert all interactions (human + Arabidopsis + real tomato)
    all_edges = human_edges + arab_edges + tomato_edges
    conn.executemany(
        "INSERT OR IGNORE INTO interactions (source_id, target_id, regulation_type, confidence, sources, pmids) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(tf, target, reg, conf, json.dumps([src]), json.dumps(pmids))
         for tf, target, reg, conf, src, pmids in all_edges],
    )
    # ---- Genome layer (optional; only populated where fetched caches exist) ----
    def load_json(path):
        return json.loads(path.read_text()) if path.exists() else {}

    # Genes for species discovered purely via orthology (mouse from OMA;
    # tomato/petunia from PLAZA). Arabidopsis/human are already inserted above.
    extra_genes = {}
    extra_genes.update(load_json(GENES_JSON))
    extra_genes.update(load_json(PLAZA_GENES_JSON))
    conn.executemany(
        "INSERT OR IGNORE INTO genes (id, symbol, name, species, is_tf, gene_type) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(gid, g.get("symbol", gid), g.get("name", gid), g["species"],
          1 if g.get("is_tf") else 0, "protein_coding")
         for gid, g in extra_genes.items()],
    )

    valid_ids = set(human_genes) | set(arab_all) | set(extra_genes)

    # Project the Arabidopsis regulatory network onto tomato/petunia via the
    # Arabidopsis->plant ortholog map: if AtTF regulates AtTarget and both have a
    # plant ortholog in the same species, infer an edge between them. Clearly
    # labeled (source "Inferred:Arabidopsis") and confidence-penalised so it is
    # never mistaken for measured regulation.
    omap = load_json(ORTHOLOG_MAP_JSON)  # {AGI(upper): {species: [plant genes]}}
    inferred_edges = []
    for tf, target, reg, conf, *_ in arab_edges:
        tf_orth = omap.get(tf.upper(), {})
        tg_orth = omap.get(target.upper(), {})
        for species in ("tomato", "petunia"):
            for a in tf_orth.get(species, []):
                for b in tg_orth.get(species, []):
                    if a != b:
                        inferred_edges.append(
                            (a, b, reg, round(conf * INFERRED_CONF_FACTOR, 2)))
    conn.executemany(
        "INSERT OR IGNORE INTO interactions (source_id, target_id, regulation_type, confidence, sources, pmids) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(a, b, reg, conf, json.dumps(["Inferred:Arabidopsis"]), "[]")
         for a, b, reg, conf in inferred_edges],
    )

    # Mark genes that act as a regulator (source of any real or inferred edge) as
    # transcription factors, so the UI badges them.
    tf_ids = {tf for tf, *_ in tomato_edges} | {a for a, *_ in inferred_edges}
    conn.executemany("UPDATE genes SET is_tf = 1 WHERE id = ?", [(t,) for t in tf_ids])

    # Coordinates: merge OMA (animal) + PLAZA (plant). PLAZA wins on overlap.
    positions = {}
    positions.update(load_json(POSITIONS_JSON))
    positions.update(load_json(PLAZA_POSITIONS_JSON))
    loc_rows = [
        (gid, p["species"], norm_chrom(p["species"], p["chromosome"]),
         int(p["start"]), int(p["end"]), int(p.get("strand", 0)))
        for gid, p in positions.items() if gid in valid_ids
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO gene_locations (gene_id, species, chromosome, start, end, strand) "
        "VALUES (?, ?, ?, ?, ?, ?)", loc_rows)

    # Chromosome lengths: authoritative where known, else max observed coord.
    observed = defaultdict(int)
    for _, species, chrom, _, end, _ in loc_rows:
        observed[(species, chrom)] = max(observed[(species, chrom)], end)
    chrom_rows = [
        (species, chrom, CHROMOSOME_LENGTHS.get(species, {}).get(chrom, obs_len))
        for (species, chrom), obs_len in observed.items()
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO chromosomes (species, chromosome, length) VALUES (?, ?, ?)",
        chrom_rows)

    # Orthologs: merge OMA + PLAZA.
    orthologs = list(load_json(ORTHOLOGS_JSON) or []) + list(load_json(PLAZA_ORTHOLOGS_JSON) or [])
    orth_rows = [
        (o["gene_a"], o["gene_b"], o["species_a"], o["species_b"], o.get("rel_type"), o.get("score"))
        for o in orthologs if o["gene_a"] in valid_ids and o["gene_b"] in valid_ids
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO orthologs (gene_a, gene_b, species_a, species_b, rel_type, score) "
        "VALUES (?, ?, ?, ?, ?, ?)", orth_rows)

    # Inferred synonyms: label tomato/petunia genes with the Arabidopsis symbol(s)
    # of their ortholog(s) -- the same principle as eggNOG's Preferred_name. Clearly
    # approximate, so kept in a separate field, never as the gene's own symbol.
    # Primary source: BHIF ortholog -> Arabidopsis symbol/alias (broad; real short
    # symbols like CHS). Supplemented by synteny-anchor orthologs to our DB.
    inferred = defaultdict(list)
    seen = defaultdict(set)

    def add_syn(gid, sym):
        if sym and sym not in seen[gid]:
            seen[gid].add(sym)
            inferred[gid].append(sym)

    for gid, syms in load_json(PLAZA_SYMBOLS_JSON).items():
        if gid in valid_ids:
            for s in syms:
                add_syn(gid, s)
    for o in orthologs:
        for gene, species, other, other_sp in (
            (o["gene_a"], o["species_a"], o["gene_b"], o["species_b"]),
            (o["gene_b"], o["species_b"], o["gene_a"], o["species_a"]),
        ):
            if species in ("tomato", "petunia") and other_sp == "arabidopsis":
                add_syn(gene, arab_real_symbol.get(other))
    conn.executemany(
        "UPDATE genes SET synonyms = ? WHERE id = ?",
        [("; ".join(syms), gid) for gid, syms in inferred.items()],
    )
    n_syn = len(inferred)

    # BLAST-curated identities: give these genes a real symbol (high-confidence
    # sequence match to a characterized regulator), overriding the locus id. This
    # is a measured identity, not an inferred synonym, so it becomes the symbol.
    # Regulators outside the atlas subset (e.g. petunia AN1) are inserted so they
    # are searchable/labelled, even without network/coordinate data.
    reg_map = []
    for p in sorted(DATA_DIR.glob("regulator_map*.json")):
        reg_map.extend(json.loads(p.read_text()))
    conn.executemany(
        "INSERT OR IGNORE INTO genes (id, symbol, name, species, is_tf, gene_type) "
        "VALUES (?, ?, ?, ?, 1, 'protein_coding')",
        [(r["gene_id"], r["name"], r.get("description", r["name"]),
          "petunia" if r["gene_id"].startswith("Peaxi") else "tomato")
         for r in reg_map if r["gene_id"] not in valid_ids],
    )
    conn.executemany(
        "UPDATE genes SET symbol = ? WHERE id = ?",
        [(r["name"], r["gene_id"]) for r in reg_map],
    )
    n_curated = len(reg_map)

    # Curated UniProt symbols (real gene names), only where no native symbol exists yet.
    for p in sorted(DATA_DIR.glob("curated_symbols_*.json")):
        sp = p.stem.replace("curated_symbols_", "")
        curated = json.loads(p.read_text())
        conn.executemany(
            "UPDATE genes SET symbol = ?, symbol_source = ? WHERE id = ? AND species = ? AND symbol = id",
            [(info["symbol"], info["source"], gid, sp) for gid, info in curated.items()])

    # GO annotations (optional; for enrichment analysis).
    go_data = {}
    if GO_JSON.exists():
        import gzip
        with gzip.open(GO_JSON, "rt", encoding="utf-8") as _f:
            go_data = json.load(_f)
    n_go_terms = n_go_ann = 0
    if go_data:
        conn.executemany(
            "INSERT OR IGNORE INTO go_terms (go_id, name, namespace) VALUES (?, ?, ?)",
            [(gid, v[0], v[1] if len(v) > 1 else "") for gid, v in go_data.get("terms", {}).items()])
        n_go_terms = len(go_data.get("terms", {}))
        ann_rows = [
            (gene_id, go_id)
            for gene_id, go_ids in go_data.get("annotations", {}).items() if gene_id in valid_ids
            for go_id in go_ids
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO go_annotations (gene_id, go_id) VALUES (?, ?)", ann_rows)
        n_go_ann = len(ann_rows)

    # Sequence-context bundle (optional). Insert row-dicts into their tables,
    # selecting the declared columns in order; missing keys become NULL.
    seqctx_counts = {}
    for table, (basename, cols) in SEQCTX_FILES.items():
        rows = load_rows(basename)
        if not rows:
            seqctx_counts[table] = 0
            continue
        conn.executemany(
            f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [tuple(r.get(c) for c in cols) for r in rows],
        )
        seqctx_counts[table] = len(rows)

    # Inferred GRN edges (optional, from infer_grn.py)
    n_inferred = 0
    for ie_file in sorted(DATA_DIR.glob("inferred_grn_*.json.gz")):
        sp = ie_file.name.split("inferred_grn_")[1].replace(".json.gz", "")
        with gzip.open(ie_file, "rt") as f:
            edges = json.load(f)
        conn.executemany(
            "INSERT OR IGNORE INTO inferred_edges "
            "(source_id, target_id, method, importance, species) "
            "VALUES (?, ?, ?, ?, ?)",
            [(e["tf"], e["target"], e["method"], e["importance"], sp)
             for e in edges],
        )
        n_inferred += len(edges)
        print(f"  Inferred GRN ({sp}): {len(edges)} edges")

    conn.commit()

    loc_by_species = defaultdict(int)
    for _, species, *_ in loc_rows:
        loc_by_species[species] += 1
    conn.close()

    print(f"  GO: {n_go_terms} terms, {n_go_ann} annotations")
    if any(seqctx_counts.values()):
        print(f"  Sequence context: {seqctx_counts}")
    print(f"  Inferred Arabidopsis-symbol synonyms on {n_syn} tomato/petunia genes")
    print(f"  BLAST-curated regulator symbols: {n_curated}")
    print(f"  Genome: {len(loc_rows)} locations, {len(orth_rows)} ortholog pairs, "
          f"{len(chrom_rows)} chromosomes")
    print(f"    by species: {dict(loc_by_species)}")
    print(f"Built {DB_PATH}:")
    print(f"  Human: {len(human_genes)} genes, {len(human_edges)} interactions")
    print(f"  Arabidopsis: {len(arab_all)} genes, {len(arab_edges)} interactions")
    print(f"  Tomato (real, PlantRegMap): {len(tomato_edges)} interactions")
    print(f"  Inferred (projected from Arabidopsis): {len(inferred_edges)} interactions")
    print(f"  Extra species genes: {len(extra_genes)}")
    print(f"  Total: {len(human_genes) + len(arab_all) + len(extra_genes)} genes")


if __name__ == "__main__":
    build()
