"""
Builds backend/data/grn.sqlite3 from local data files committed to the repo.

Human data: TRRUST v2 TSV + gene_names.json (from mygene.info)
Arabidopsis data: PlantRegMap filtered TSV + gene_names_arabidopsis.json
ATRM direction labels: atrm_regulations.tsv (activation/repression for 1,431 literature-curated pairs)

No network access needed. Safe to re-run; always rebuilds from scratch.
"""
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


def load_human_edges():
    """Parse TRRUST, merging duplicate (tf, target) pairs across papers."""
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
        total_refs = len(d["Activation"] | d["Repression"])
        confidence = round(min(0.5 + 0.1 * total_refs, 0.95), 2)
        edges.append((tf, target, reg, confidence, "TRRUST"))
    return edges


def load_atrm_directions():
    """Load ATRM literature-curated direction labels (A/R/D)."""
    directions = {}
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
            edges.append((tf, target, reg, confidence, "PlantRegMap"))
    print(f"  ATRM: set direction on {directed}/{len(atrm)} literature-curated pairs")
    return edges


def build():
    # Load edges
    human_edges = load_human_edges()
    arab_edges = load_arabidopsis_edges()

    # Load gene names
    human_names = json.loads(HUMAN_NAMES_JSON.read_text())
    arab_names = json.loads(ARABIDOPSIS_NAMES_JSON.read_text())

    # Human genes
    human_tfs = {tf for tf, _, _, _, _ in human_edges}
    human_genes = sorted(human_tfs | {t for _, t, _, _, _ in human_edges})

    # Arabidopsis genes
    arab_tfs = {tf for tf, _, _, _, _ in arab_edges}
    arab_all = sorted(arab_tfs | {t for _, t, _, _, _ in arab_edges})

    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE genes (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            species TEXT NOT NULL,
            is_tf INTEGER NOT NULL,
            gene_type TEXT
        );
        CREATE INDEX idx_genes_symbol ON genes(symbol COLLATE NOCASE);
        CREATE INDEX idx_genes_name ON genes(name COLLATE NOCASE);
        CREATE INDEX idx_genes_species ON genes(species);

        CREATE TABLE interactions (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            regulation_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            sources TEXT NOT NULL,
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
    conn.executemany(
        "INSERT INTO genes (id, symbol, name, species, is_tf, gene_type) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                locus,
                arab_names.get(locus, {}).get("symbol", locus) if isinstance(arab_names.get(locus), dict) else locus,
                arab_names.get(locus, {}).get("name", locus) if isinstance(arab_names.get(locus), dict) else locus,
                "arabidopsis",
                1 if locus in arab_tfs else 0,
                "protein_coding",
            )
            for locus in arab_all
        ],
    )

    # Insert all interactions
    all_edges = human_edges + arab_edges
    conn.executemany(
        "INSERT OR IGNORE INTO interactions (source_id, target_id, regulation_type, confidence, sources) VALUES (?, ?, ?, ?, ?)",
        [(tf, target, reg, conf, json.dumps([src])) for tf, target, reg, conf, src in all_edges],
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

    # Coordinates: merge OMA (animal) + PLAZA (plant). PLAZA wins on overlap.
    # Normalize chromosome names to a canonical short form so different sources
    # and assemblies agree: OMA calls Arabidopsis chr 1 "1" but PLAZA calls it
    # "Chr1"; tomato's SL2.50 GFF names it "SL2.50ch01". Reduce both to "1".
    def norm_chrom(species, name):
        name = str(name)
        if species == "tomato":
            m = re.search(r"ch0*(\d+)$", name)
            if m:
                return m.group(1)
        return re.sub(r"^chr", "", name, flags=re.IGNORECASE)

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

    conn.commit()

    loc_by_species = defaultdict(int)
    for _, species, *_ in loc_rows:
        loc_by_species[species] += 1
    conn.close()

    print(f"  Genome: {len(loc_rows)} locations, {len(orth_rows)} ortholog pairs, "
          f"{len(chrom_rows)} chromosomes")
    print(f"    by species: {dict(loc_by_species)}")
    print(f"Built {DB_PATH}:")
    print(f"  Human: {len(human_genes)} genes, {len(human_edges)} interactions")
    print(f"  Arabidopsis: {len(arab_all)} genes, {len(arab_edges)} interactions")
    print(f"  Extra species genes: {len(extra_genes)}")
    print(f"  Total: {len(human_genes) + len(arab_all) + len(extra_genes)} genes")


if __name__ == "__main__":
    build()
