"""Load the human/mouse pathway caches into grn.sqlite3 additively (INSERT OR IGNORE),
without touching the plant Reactome rows. No full rebuild needed.
"""
import gzip
import json
import sqlite3
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
DB = DATA / "grn.sqlite3"


def main():
    conn = sqlite3.connect(DB)
    pathways = json.loads((DATA / "pathways_animal.json").read_text())
    with gzip.open(DATA / "pathway_annotations_animal.json.gz", "rt", encoding="utf-8") as f:
        annos = json.load(f)
    conn.executemany("INSERT OR IGNORE INTO pathways (pathway_id, name, source) VALUES (?,?,?)",
                     [(p["pathway_id"], p["name"], p["source"]) for p in pathways])
    conn.executemany("INSERT OR IGNORE INTO pathway_annotations (gene_id, pathway_id) VALUES (?,?)",
                     [(a["gene_id"], a["pathway_id"]) for a in annos])
    conn.commit()
    print(f"loaded pathways={len(pathways)} annotations={len(annos)}")
    conn.close()


if __name__ == "__main__":
    main()
