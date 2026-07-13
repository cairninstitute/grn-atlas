"""Targeted loader for pathway annotations (#5) into grn.sqlite3 — no full rebuild.
Idempotent: recreates the pathway tables from the committed caches.
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
        CREATE TABLE IF NOT EXISTS pathways (
            pathway_id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pathway_annotations (
            gene_id TEXT NOT NULL, pathway_id TEXT NOT NULL,
            PRIMARY KEY (gene_id, pathway_id));
        CREATE INDEX IF NOT EXISTS idx_pathway_anno_gene ON pathway_annotations(gene_id);
    """)
    pathways = json.loads((DATA / "pathways.json").read_text())
    with gzip.open(DATA / "pathway_annotations.json.gz", "rt", encoding="utf-8") as f:
        annos = json.load(f)
    conn.execute("DELETE FROM pathways")
    conn.execute("DELETE FROM pathway_annotations")
    conn.executemany("INSERT OR REPLACE INTO pathways (pathway_id, name, source) VALUES (?,?,?)",
                     [(p["pathway_id"], p["name"], p["source"]) for p in pathways])
    conn.executemany("INSERT OR IGNORE INTO pathway_annotations (gene_id, pathway_id) VALUES (?,?)",
                     [(a["gene_id"], a["pathway_id"]) for a in annos])
    conn.commit()
    print(f"loaded pathways={len(pathways)} annotations={len(annos)}")
    conn.close()


if __name__ == "__main__":
    main()
