"""
Builds backend/data/grn.sqlite3 from local data files committed to the repo.

Human data: TRRUST v2 TSV + gene_names.json (from mygene.info)
Arabidopsis data: PlantRegMap filtered TSV + gene_names_arabidopsis.json
ATRM direction labels: atrm_regulations.tsv (activation/repression for 1,431 literature-curated pairs)

No network access needed. Safe to re-run; always rebuilds from scratch.
"""
import json
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
    conn.commit()
    conn.close()

    print(f"Built {DB_PATH}:")
    print(f"  Human: {len(human_genes)} genes, {len(human_edges)} interactions")
    print(f"  Arabidopsis: {len(arab_all)} genes, {len(arab_edges)} interactions")
    print(f"  Total: {len(human_genes) + len(arab_all)} genes, {len(all_edges)} interactions")


if __name__ == "__main__":
    build()
