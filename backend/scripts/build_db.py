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

# Human (TRRUST v2 + DoRothEA)
TRRUST_TSV = DATA_DIR / "trrust_rawdata.human.tsv"
HUMAN_NAMES_JSON = DATA_DIR / "gene_names.json"
HUMAN_GENES_JSON = DATA_DIR / "gene_list_human.json"

# Mouse (TRRUST v2 + DoRothEA)
TRRUST_MOUSE_TSV = DATA_DIR / "trrust_rawdata.mouse.tsv"
MOUSE_GENES_JSON = DATA_DIR / "gene_list_mouse.json"
DOROTHEA_MOUSE_TSV = DATA_DIR / "dorothea_mouse.tsv"

# Arabidopsis (PlantRegMap, filtered to literature + ChIP-seq + FunTFBS)
ARABIDOPSIS_TSV = DATA_DIR / "regulation_arabidopsis.tsv"
ARABIDOPSIS_NAMES_JSON = DATA_DIR / "gene_names_arabidopsis.json"

# Tomato / petunia / potato (PlantRegMap; see fetch_plantregmap_regulation.py). Optional.
TOMATO_TSV = DATA_DIR / "regulation_tomato.tsv"
PETUNIA_TSV = DATA_DIR / "regulation_petunia.tsv"
POTATO_TSV = DATA_DIR / "regulation_potato.tsv"
# Arabidopsis->plant ortholog map for projecting the network onto tomato/petunia.
ORTHOLOG_MAP_JSON = DATA_DIR / "ortholog_map_plaza.json"
INFERRED_CONF_FACTOR = 0.7   # confidence penalty for orthology-projected edges
SOLANACEAE_CONF_FACTOR = 0.85  # higher confidence for Solanaceae-to-Solanaceae projection
TOBACCO_CONF_FACTOR = 0.80   # tobacco→petunia/tomato via BLAST RBH orthologs

TOBACCO_TSV = DATA_DIR / "regulation_tobacco_raw.tsv"
TOBACCO_ORTHOLOGS_JSON = DATA_DIR / "orthologs_tobacco_blast.json"

# ATRM direction labels (literature-curated activation/repression)
ATRM_TSV = DATA_DIR / "atrm_regulations.tsv"

# DAP-seq direct binding (Plant Cistrome, O'Malley et al. 2016). Optional.
DAPSEQ_TSV = DATA_DIR / "dapseq_arabidopsis.tsv"

# Rice PlantRegMap regulation (raw format, no atlas gene mapping needed)
RICE_TSV = DATA_DIR / "regulation_rice_raw.tsv"

# DoRothEA human TF-target edges (OmniPath; A+B confidence). Optional second source.
DOROTHEA_TSV = DATA_DIR / "dorothea_human.tsv"

# Pepper PlantRegMap regulation (not available on PlantRegMap; pepper gets edges
# only from Arabidopsis/tobacco projection)
PEPPER_TSV = DATA_DIR / "regulation_pepper.tsv"

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


def _load_dorothea(tsv_path, species_label, id_fn=None):
    """Parse DoRothEA TF-target edges (A+B confidence from OmniPath)."""
    if not tsv_path.exists():
        print(f"  (skip) {tsv_path.name} not fetched — DoRothEA {species_label} empty")
        return []
    if id_fn is None:
        id_fn = lambda x: x
    edges = []
    with open(tsv_path) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            tf, target, reg, conf = parts[0], parts[1], parts[2], float(parts[3])
            edges.append((id_fn(tf), id_fn(target), reg, conf, "DoRothEA", []))
    print(f"  DoRothEA: {len(edges)} {species_label} edges")
    return edges


def load_dorothea_edges():
    return _load_dorothea(DOROTHEA_TSV, "human")


def _mouse_id(sym):
    return f"mouse:{sym}"


def load_mouse_edges():
    """Parse TRRUST mouse, same format as human. IDs prefixed with mouse:."""
    if not TRRUST_MOUSE_TSV.exists():
        print(f"  (skip) {TRRUST_MOUSE_TSV.name} not fetched — mouse TRRUST empty")
        return []
    pair_data = defaultdict(lambda: {"Activation": set(), "Repression": set()})
    with open(TRRUST_MOUSE_TSV) as f:
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
        edges.append((_mouse_id(tf), _mouse_id(target), reg, confidence, "TRRUST", pmids))
    print(f"  TRRUST mouse: {len(edges)} edges")
    return edges


def load_dorothea_mouse_edges():
    return _load_dorothea(DOROTHEA_MOUSE_TSV, "mouse", id_fn=_mouse_id)


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
    """Parse filtered PlantRegMap TSV, overlaying ATRM direction labels.

    Returns two lists: PlantRegMap edges and ATRM-only edges (as a second
    source for multi-evidence merging)."""
    atrm = load_atrm_directions()
    edges = []
    atrm_edges = []
    seen = set()
    directed = 0
    if not ARABIDOPSIS_TSV.exists():
        print(f"  (skip) {ARABIDOPSIS_TSV.name} not fetched — arabidopsis network empty")
        return edges, atrm_edges
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
                atrm_edges.append((tf, target, reg, 0.92, "ATRM", []))
            edges.append((tf, target, reg, confidence, "PlantRegMap", []))
    print(f"  ATRM: {directed}/{len(atrm)} literature-curated pairs (added as second source)")
    return edges, atrm_edges


def load_tomato_edges():
    """Real tomato TF-target edges from PlantRegMap FunTFBS (optional file)."""
    return load_plantregmap_edges(TOMATO_TSV)


def load_plantregmap_edges(tsv_path):
    """Load TF-target edges from a regulation TSV (optional file).
    Supports both PlantRegMap and curated literature entries."""
    if not tsv_path.exists():
        return []
    edges = []
    with open(tsv_path) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            tf, target, reg, conf = parts[0], parts[1], parts[2], float(parts[3])
            src = parts[4] if len(parts) > 4 else "PlantRegMap"
            if src.startswith("literature"):
                pmid = src.split(":", 1)[1] if ":" in src else ""
                edges.append((tf, target, reg, conf, "Literature", [pmid] if pmid else []))
            else:
                edges.append((tf, target, reg, conf, "PlantRegMap", []))
    return edges


def load_dapseq_edges():
    """Load DAP-seq TF-target binding edges (Plant Cistrome, O'Malley 2016)."""
    if not DAPSEQ_TSV.exists():
        print("  (skip) dapseq_arabidopsis.tsv not fetched — DAP-seq empty")
        return []
    edges = []
    with open(DAPSEQ_TSV) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            tf, target, reg, conf, src = parts[0], parts[1], parts[2], float(parts[3]), parts[4]
            pmids = [parts[5]] if len(parts) > 5 and parts[5] else []
            edges.append((tf, target, reg, conf, src, pmids))
    print(f"  DAP-seq: {len(edges):,} arabidopsis binding edges")
    return edges


def load_rice_edges():
    """Load rice PlantRegMap edges (raw format with pre-stripped IDs)."""
    return load_plantregmap_edges(RICE_TSV)


def load_tobacco_edges(tsv_path):
    """Load tobacco PlantRegMap edges (raw format: TF, regulates, target, motif, species, -, -)."""
    if not tsv_path.exists():
        return []
    edges = []
    with open(tsv_path) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            tf, target = parts[0], parts[2]
            edges.append((tf, target, "regulation", 0.65, "PlantRegMap", []))
    return edges


def build():
    # Load edges
    human_edges = load_human_edges()
    dorothea_edges = load_dorothea_edges()
    mouse_edges = load_mouse_edges()
    dorothea_mouse_edges = load_dorothea_mouse_edges()
    arab_edges, atrm_edges = load_arabidopsis_edges()
    dapseq_edges = load_dapseq_edges()
    tomato_edges = load_tomato_edges()
    petunia_edges = load_plantregmap_edges(PETUNIA_TSV)
    potato_edges = load_plantregmap_edges(POTATO_TSV)
    pepper_edges = load_plantregmap_edges(PEPPER_TSV)
    rice_edges = load_rice_edges()

    # Load gene names (optional; fall back to bare ids if not fetched)
    human_names = json.loads(HUMAN_NAMES_JSON.read_text()) if HUMAN_NAMES_JSON.exists() else {}
    arab_names = json.loads(ARABIDOPSIS_NAMES_JSON.read_text()) if ARABIDOPSIS_NAMES_JSON.exists() else {}

    # Broader gene lists (protein-coding, from mygene.info)
    human_gene_list = json.loads(HUMAN_GENES_JSON.read_text()) if HUMAN_GENES_JSON.exists() else {}
    mouse_gene_list = json.loads(MOUSE_GENES_JSON.read_text()) if MOUSE_GENES_JSON.exists() else {}

    # Human genes: union of edge genes + comprehensive gene list
    human_edge_genes = ({tf for tf, *_ in human_edges} | {e[1] for e in human_edges}
                        | {tf for tf, *_ in dorothea_edges} | {e[1] for e in dorothea_edges})
    human_tfs = {tf for tf, *_ in human_edges} | {tf for tf, *_ in dorothea_edges}
    human_genes = sorted(human_edge_genes | set(human_gene_list.keys()))
    human_names.update(human_gene_list)

    # Mouse genes: union of edge genes + comprehensive gene list
    mouse_edge_genes = ({tf for tf, *_ in mouse_edges} | {e[1] for e in mouse_edges}
                        | {tf for tf, *_ in dorothea_mouse_edges} | {e[1] for e in dorothea_mouse_edges})
    mouse_tfs = {tf for tf, *_ in mouse_edges} | {tf for tf, *_ in dorothea_mouse_edges}
    mouse_genes = sorted(mouse_edge_genes | {_mouse_id(k) for k in mouse_gene_list})

    # Arabidopsis genes (PlantRegMap + ATRM + DAP-seq)
    arab_tfs = {tf for tf, *_ in arab_edges} | {tf for tf, *_ in dapseq_edges}
    arab_all = sorted(arab_tfs | {e[1] for e in arab_edges} | {e[1] for e in dapseq_edges})

    # Rice genes
    rice_tfs = {tf for tf, *_ in rice_edges}
    rice_all = sorted(rice_tfs | {e[1] for e in rice_edges})

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

        CREATE TABLE edge_tissue_weights (
            source_id     TEXT NOT NULL,
            target_id     TEXT NOT NULL,
            tissue        TEXT NOT NULL,
            coexpression  REAL NOT NULL,
            species       TEXT NOT NULL,
            PRIMARY KEY (source_id, target_id, tissue)
        );
        CREATE INDEX idx_etw_source ON edge_tissue_weights(source_id);
        CREATE INDEX idx_etw_species ON edge_tissue_weights(species);

        -- M1: imported omics datasets
        CREATE TABLE imported_datasets (
            dataset_id    TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            species       TEXT NOT NULL,
            data_type     TEXT NOT NULL,  -- 'bulk', 'pseudobulk', 'scRNA', 'scATAC'
            n_features    INTEGER NOT NULL DEFAULT 0,
            n_samples     INTEGER NOT NULL DEFAULT 0,
            n_clusters    INTEGER NOT NULL DEFAULT 0,
            metadata      TEXT,           -- JSON blob
            created_at    TEXT NOT NULL,
            provenance    TEXT            -- JSON: source, method, version
        );

        CREATE TABLE imported_features (
            dataset_id  TEXT NOT NULL,
            gene_id     TEXT NOT NULL,
            mean_expr   REAL,
            pct_cells   REAL,
            PRIMARY KEY (dataset_id, gene_id),
            FOREIGN KEY (dataset_id) REFERENCES imported_datasets(dataset_id)
        );

        CREATE TABLE imported_clusters (
            dataset_id   TEXT NOT NULL,
            cluster_id   TEXT NOT NULL,
            cluster_name TEXT,
            n_cells      INTEGER NOT NULL DEFAULT 0,
            metadata     TEXT,
            PRIMARY KEY (dataset_id, cluster_id),
            FOREIGN KEY (dataset_id) REFERENCES imported_datasets(dataset_id)
        );

        CREATE TABLE imported_contrasts (
            dataset_id    TEXT NOT NULL,
            contrast_id   TEXT PRIMARY KEY,
            group_a       TEXT NOT NULL,
            group_b       TEXT NOT NULL,
            n_deg_up      INTEGER NOT NULL DEFAULT 0,
            n_deg_down    INTEGER NOT NULL DEFAULT 0,
            metadata      TEXT,
            FOREIGN KEY (dataset_id) REFERENCES imported_datasets(dataset_id)
        );

        CREATE TABLE imported_deg (
            contrast_id   TEXT NOT NULL,
            gene_id       TEXT NOT NULL,
            log2fc        REAL NOT NULL,
            pvalue        REAL,
            padj          REAL,
            PRIMARY KEY (contrast_id, gene_id),
            FOREIGN KEY (contrast_id) REFERENCES imported_contrasts(contrast_id)
        );
        CREATE INDEX idx_ideg_contrast ON imported_deg(contrast_id);

        -- M4: chromatin / enhancer regulatory layer
        CREATE TABLE chromatin_peaks (
            peak_id     TEXT PRIMARY KEY,
            species     TEXT NOT NULL,
            chrom       TEXT NOT NULL,
            start_pos   INTEGER NOT NULL,
            end_pos     INTEGER NOT NULL,
            summit      INTEGER,
            score       REAL,
            peak_type   TEXT,          -- 'promoter', 'enhancer', 'distal'
            dataset_id  TEXT,
            FOREIGN KEY (dataset_id) REFERENCES imported_datasets(dataset_id)
        );
        CREATE INDEX idx_peaks_species ON chromatin_peaks(species);
        CREATE INDEX idx_peaks_chrom ON chromatin_peaks(chrom);

        CREATE TABLE peak_gene_links (
            peak_id       TEXT NOT NULL,
            gene_id       TEXT NOT NULL,
            link_score    REAL NOT NULL,
            link_type     TEXT NOT NULL,  -- 'correlation', 'proximity', 'activity'
            distance_bp   INTEGER,
            species       TEXT NOT NULL,
            dataset_id    TEXT,
            PRIMARY KEY (peak_id, gene_id),
            FOREIGN KEY (peak_id) REFERENCES chromatin_peaks(peak_id)
        );
        CREATE INDEX idx_pgl_gene ON peak_gene_links(gene_id);
        CREATE INDEX idx_pgl_species ON peak_gene_links(species);

        CREATE TABLE peak_motif_hits (
            peak_id     TEXT NOT NULL,
            motif_id    TEXT NOT NULL,
            tf_gene_id  TEXT,
            score       REAL NOT NULL,
            pvalue      REAL,
            position    INTEGER,
            strand      TEXT,
            PRIMARY KEY (peak_id, motif_id, position),
            FOREIGN KEY (peak_id) REFERENCES chromatin_peaks(peak_id)
        );
        CREATE INDEX idx_pmh_tf ON peak_motif_hits(tf_gene_id);

        CREATE TABLE cis_support_edges (
            source_id   TEXT NOT NULL,
            target_id   TEXT NOT NULL,
            peak_id     TEXT,
            support_type TEXT NOT NULL,  -- 'motif_in_peak', 'peak_gene_link', 'enhancer'
            score       REAL NOT NULL,
            species     TEXT NOT NULL,
            PRIMARY KEY (source_id, target_id, peak_id),
            FOREIGN KEY (peak_id) REFERENCES chromatin_peaks(peak_id)
        );
        CREATE INDEX idx_cse_source ON cis_support_edges(source_id);
        CREATE INDEX idx_cse_target ON cis_support_edges(target_id);
    """)

    # Insert human genes
    conn.executemany(
        "INSERT INTO genes (id, symbol, name, species, is_tf, gene_type) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (sym, sym, human_names.get(sym, sym), "human", 1 if sym in human_tfs else 0, "protein_coding")
            for sym in human_genes
        ],
    )

    # Insert mouse genes (prefixed with mouse: to avoid collision with human symbols)
    conn.executemany(
        "INSERT INTO genes (id, symbol, name, species, is_tf, gene_type) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (gid, gid.removeprefix("mouse:"), mouse_gene_list.get(gid.removeprefix("mouse:"), gid.removeprefix("mouse:")),
             "mouse", 1 if gid in mouse_tfs else 0, "protein_coding")
            for gid in mouse_genes
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
    # Insert rice genes
    if rice_all:
        conn.executemany(
            "INSERT INTO genes (id, symbol, name, species, is_tf, gene_type) VALUES (?, ?, ?, ?, ?, ?)",
            [(gid, gid, gid, "rice", 1 if gid in rice_tfs else 0, "protein_coding")
             for gid in rice_all],
        )

    # Real Arabidopsis symbols (excluding bare AGI ids), for inferring synonyms.
    arab_real_symbol = {
        locus: arab_symbol(locus) for locus in arab_all
        if arab_symbol(locus).upper() != locus.upper()
    }

    # Collect all edges into a merge dict keyed by (source_id, target_id).
    # Each source contributes its confidence, source label, and pmids.
    # After all sources are collected, we merge and insert once.
    merged_edges = {}  # (src_id, tgt_id) -> {reg, conf, sources: set, pmids: set}

    def add_edges(edges, default_source=None):
        for tf, target, reg, conf, *rest in edges:
            src = rest[0] if rest else default_source or "Unknown"
            pmids = rest[1] if len(rest) > 1 else []
            key = (tf, target)
            if key not in merged_edges:
                merged_edges[key] = {"reg": reg, "conf": conf, "sources": set(), "pmids": set()}
            entry = merged_edges[key]
            entry["conf"] = max(entry["conf"], conf)
            entry["sources"].add(src)
            for p in (pmids if isinstance(pmids, list) else [pmids]):
                if p:
                    entry["pmids"].add(p)

    add_edges(human_edges)
    add_edges(dorothea_edges)
    add_edges(mouse_edges)
    add_edges(dorothea_mouse_edges)
    add_edges(arab_edges)
    add_edges(atrm_edges)
    add_edges(dapseq_edges)
    add_edges(rice_edges)
    add_edges(tomato_edges)
    add_edges(petunia_edges)
    add_edges(potato_edges)
    add_edges(pepper_edges)
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

    valid_ids = set(human_genes) | set(mouse_genes) | set(arab_all) | set(rice_all) | set(extra_genes)

    # Ensure curated-edge gene IDs that aren't in PLAZA are added to the genes table.
    curated_syms = {}
    for sp in ("petunia", "tomato", "potato"):
        sym_path = DATA_DIR / f"curated_symbols_{sp}.json"
        if sym_path.exists():
            curated_syms.update({gid: (info, sp) for gid, info in json.loads(sym_path.read_text()).items()})
    all_edge_ids = set()
    for edges in (tomato_edges, petunia_edges, potato_edges):
        for tf, target, *_ in edges:
            all_edge_ids.add(tf)
            all_edge_ids.add(target)
    missing = all_edge_ids - valid_ids
    if missing:
        stub_rows = []
        for gid in missing:
            info, sp = curated_syms.get(gid, ({}, "petunia" if gid.startswith("Peaxi") else "tomato"))
            stub_rows.append((gid, info.get("symbol", gid), gid, sp, 0, "protein_coding"))
        conn.executemany(
            "INSERT OR IGNORE INTO genes (id, symbol, name, species, is_tf, gene_type) "
            "VALUES (?, ?, ?, ?, ?, ?)", stub_rows)
        valid_ids.update(missing)
        print(f"  Added {len(stub_rows)} stub genes from curated edges")

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
        for species in ("tomato", "petunia", "pepper", "rice"):
            for a in tf_orth.get(species, []):
                for b in tg_orth.get(species, []):
                    if a != b:
                        inferred_edges.append(
                            (a, b, reg, round(conf * INFERRED_CONF_FACTOR, 2),
                             "Inferred:Arabidopsis", []))
    add_edges(inferred_edges)

    # Project potato regulatory edges onto petunia/tomato. Two mapping sources:
    # 1. Arabidopsis bridge: potato→Ath ortholog→petunia/tomato ortholog
    # 2. Direct PLAZA synteny pairs: potato↔petunia, potato↔tomato
    # Direct synteny recovers genes that lack Arabidopsis orthologs.
    potato_to_plant = defaultdict(lambda: defaultdict(set))  # {potato_id: {species: {plant_ids}}}
    for agi, sp_map in omap.items():
        potato_ids = sp_map.get("potato", [])
        if not potato_ids:
            continue
        for target_sp in ("tomato", "petunia"):
            target_ids = sp_map.get(target_sp, [])
            if not target_ids:
                continue
            for pot_id in potato_ids:
                for tgt_id in target_ids:
                    potato_to_plant[pot_id][target_sp].add(tgt_id)

    # Supplement with direct synteny pairs from PLAZA orthologs JSON,
    # and use pepper as a bridge: potato→pepper→petunia/tomato
    plaza_orthologs = list(load_json(PLAZA_ORTHOLOGS_JSON) or [])
    pepper_to_plant = defaultdict(lambda: defaultdict(set))
    potato_to_pepper = defaultdict(set)
    for o in plaza_orthologs:
        sa, sb = o["species_a"], o["species_b"]
        if sa == "potato" and sb in ("petunia", "tomato"):
            potato_to_plant[o["gene_a"]][sb].add(o["gene_b"])
        elif sb == "potato" and sa in ("petunia", "tomato"):
            potato_to_plant[o["gene_b"]][sa].add(o["gene_a"])
        elif sa == "potato" and sb == "pepper":
            potato_to_pepper[o["gene_a"]].add(o["gene_b"])
        elif sb == "potato" and sa == "pepper":
            potato_to_pepper[o["gene_b"]].add(o["gene_a"])
        elif sa == "pepper" and sb in ("petunia", "tomato"):
            pepper_to_plant[o["gene_a"]][sb].add(o["gene_b"])
        elif sb == "pepper" and sa in ("petunia", "tomato"):
            pepper_to_plant[o["gene_b"]][sa].add(o["gene_a"])
    # Bridge: potato→pepper→petunia/tomato
    for pot_id, pepper_ids in potato_to_pepper.items():
        for pep_id in pepper_ids:
            for sp, tgt_ids in pepper_to_plant.get(pep_id, {}).items():
                potato_to_plant[pot_id][sp].update(tgt_ids)

    solanaceae_inferred = []
    for tf, target, reg, conf, *_ in potato_edges:
        tf_map = potato_to_plant.get(tf, {})
        tg_map = potato_to_plant.get(target, {})
        for species in ("tomato", "petunia", "pepper"):
            for a in tf_map.get(species, set()):
                for b in tg_map.get(species, set()):
                    if a != b:
                        solanaceae_inferred.append(
                            (a, b, reg, round(conf * SOLANACEAE_CONF_FACTOR, 2),
                             "Inferred:Potato", []))
    add_edges(solanaceae_inferred)
    print(f"  Inferred (projected from potato): {len(solanaceae_inferred)} interactions")

    # Project tobacco regulatory edges onto petunia/tomato via BLAST RBH orthologs
    tobacco_orthologs = load_json(TOBACCO_ORTHOLOGS_JSON) if TOBACCO_ORTHOLOGS_JSON.exists() else []
    tobacco_to_plant = defaultdict(lambda: defaultdict(set))
    for o in (tobacco_orthologs or []):
        tobacco_to_plant[o["gene_a"]][o["species_b"]].add(o["gene_b"])

    tobacco_edges = load_tobacco_edges(TOBACCO_TSV)
    tobacco_inferred = []
    for tf, target, reg, conf, *_ in tobacco_edges:
        tf_map = tobacco_to_plant.get(tf, {})
        tg_map = tobacco_to_plant.get(target, {})
        for species in ("tomato", "petunia", "pepper"):
            for a in tf_map.get(species, set()):
                for b in tg_map.get(species, set()):
                    if a != b and a in valid_ids and b in valid_ids:
                        tobacco_inferred.append(
                            (a, b, reg, round(conf * TOBACCO_CONF_FACTOR, 2),
                             "Inferred:Tobacco", []))
    add_edges(tobacco_inferred)
    print(f"  Inferred (projected from tobacco): {len(tobacco_inferred)} interactions")

    # Apply multi-evidence confidence boost and insert all merged interactions
    MULTI_EVIDENCE_BOOST = 0.05
    insert_rows = []
    for (src_id, tgt_id), entry in merged_edges.items():
        n_sources = len(entry["sources"])
        conf = entry["conf"]
        if n_sources > 1:
            conf = min(conf + MULTI_EVIDENCE_BOOST * (n_sources - 1), 0.99)
        insert_rows.append((
            src_id, tgt_id, entry["reg"], round(conf, 4),
            json.dumps(sorted(entry["sources"])),
            json.dumps(sorted(entry["pmids"])),
        ))
    conn.executemany(
        "INSERT OR IGNORE INTO interactions (source_id, target_id, regulation_type, confidence, sources, pmids) "
        "VALUES (?, ?, ?, ?, ?, ?)", insert_rows,
    )
    multi_src = sum(1 for e in merged_edges.values() if len(e["sources"]) > 1)
    print(f"  Multi-evidence edges: {multi_src:,} pairs supported by 2+ sources")

    # Mark genes that act as a regulator (source of any real or inferred edge) as
    # transcription factors, so the UI badges them.
    tf_ids = ({tf for tf, *_ in tomato_edges} | {tf for tf, *_ in petunia_edges}
              | {tf for tf, *_ in potato_edges} | {tf for tf, *_ in pepper_edges}
              | {a for a, *_ in inferred_edges} | {a for a, *_ in solanaceae_inferred}
              | {a for a, *_ in tobacco_inferred})
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

    # Suppress edges that match gold standard negative controls.
    # Runs after synonyms are populated so resolve_symbol can find gene symbols.
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from validate_regulation_quality import resolve_symbol
    for sp in ("petunia", "tomato"):
        gs_path = DATA_DIR / f"gold_standard_{sp}.tsv"
        if not gs_path.exists():
            continue
        suppressed = 0
        with open(gs_path) as f:
            f.readline()
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) < 3 or parts[2] != "negative_control":
                    continue
                tf_ids = resolve_symbol(conn, sp, parts[0])
                tgt_ids = resolve_symbol(conn, sp, parts[1])
                for tf_id in tf_ids:
                    for tgt_id in tgt_ids:
                        cur = conn.execute(
                            "DELETE FROM interactions WHERE source_id=? AND target_id=?",
                            (tf_id, tgt_id))
                        cur2 = conn.execute(
                            "DELETE FROM inferred_edges WHERE source_id=? AND target_id=?",
                            (tf_id, tgt_id))
                        suppressed += cur.rowcount + cur2.rowcount
        if suppressed:
            print(f"  Suppressed {suppressed} negative-control edges for {sp}")
    conn.commit()

    loc_by_species = defaultdict(int)
    for _, species, *_ in loc_rows:
        loc_by_species[species] += 1
    total_interactions = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
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
    print(f"  Human: {len(human_genes):,} genes, {len(human_edges)} TRRUST + {len(dorothea_edges)} DoRothEA")
    print(f"  Mouse: {len(mouse_genes):,} genes, {len(mouse_edges)} TRRUST + {len(dorothea_mouse_edges)} DoRothEA")
    print(f"  Arabidopsis: {len(arab_all):,} genes, {len(arab_edges)} PlantRegMap + {len(atrm_edges)} ATRM + {len(dapseq_edges):,} DAP-seq")
    print(f"  Rice: {len(rice_all):,} genes, {len(rice_edges)} PlantRegMap + Arabidopsis projection")
    print(f"  Tomato: {len(tomato_edges)} PlantRegMap edges")
    print(f"  Petunia: {len(petunia_edges)} PlantRegMap edges")
    print(f"  Potato: {len(potato_edges)} PlantRegMap edges")
    print(f"  Pepper: {len(pepper_edges)} direct edges + Arabidopsis/potato projection")
    print(f"  Inferred: Arabidopsis={len(inferred_edges):,}, potato={len(solanaceae_inferred):,}, tobacco={len(tobacco_inferred):,}")
    total_genes = len(human_genes) + len(mouse_genes) + len(arab_all) + len(rice_all) + len(extra_genes)
    print(f"  Total: {total_interactions:,} interactions, {total_genes:,} genes")


if __name__ == "__main__":
    build()
