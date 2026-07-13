"""Targeted loader for gene-trait associations (#5) into grn.sqlite3 — no full rebuild.
Idempotent: recreates the table from the committed cache.
"""
import gzip
import json
import sqlite3
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
DB = DATA / "grn.sqlite3"


def main():
    conn = sqlite3.connect(DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trait_associations (
            gene_id   TEXT NOT NULL,
            trait     TEXT NOT NULL,
            pubmed_id TEXT,
            source    TEXT NOT NULL DEFAULT 'GWAS Catalog',
            PRIMARY KEY (gene_id, trait));
        CREATE INDEX IF NOT EXISTS idx_trait_gene ON trait_associations(gene_id);
    """)
    with gzip.open(DATA / "trait_associations.json.gz", "rt", encoding="utf-8") as f:
        annos = json.load(f)
    conn.execute("DELETE FROM trait_associations")
    conn.executemany(
        "INSERT OR IGNORE INTO trait_associations (gene_id, trait, pubmed_id) VALUES (?,?,?)",
        [(a["gene_id"], a["trait"], a.get("pubmed_id")) for a in annos])
    conn.commit()
    print(f"loaded trait associations={len(annos)}")
    conn.close()


if __name__ == "__main__":
    main()
