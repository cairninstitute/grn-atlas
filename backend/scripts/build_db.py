"""
Builds backend/data/grn.sqlite3 from the local TRRUST TSV and the cached
gene-name lookup, both committed to the repo so no network access is
needed at build or run time. Safe to re-run; always rebuilds from scratch.
"""
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
TRRUST_TSV = DATA_DIR / "trrust_rawdata.human.tsv"
GENE_NAMES_JSON = DATA_DIR / "gene_names.json"
DB_PATH = DATA_DIR / "grn.sqlite3"


def load_edges():
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
        edges.append((tf, target, reg, confidence))
    return edges


def build():
    edges = load_edges()
    all_tfs = {tf for tf, _, _, _ in edges}
    all_genes = sorted(all_tfs | {target for _, target, _, _ in edges})
    names = json.loads(GENE_NAMES_JSON.read_text())

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

    conn.executemany(
        "INSERT INTO genes (id, symbol, name, species, is_tf, gene_type) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (symbol, symbol, names.get(symbol, symbol), "human", 1 if symbol in all_tfs else 0, "protein_coding")
            for symbol in all_genes
        ],
    )
    conn.executemany(
        "INSERT INTO interactions (source_id, target_id, regulation_type, confidence, sources) VALUES (?, ?, ?, ?, ?)",
        [(tf, target, reg, conf, json.dumps(["TRRUST"])) for tf, target, reg, conf in edges],
    )
    conn.commit()
    conn.close()

    print(f"Built {DB_PATH}: {len(all_genes)} genes, {len(edges)} interactions")


if __name__ == "__main__":
    build()
