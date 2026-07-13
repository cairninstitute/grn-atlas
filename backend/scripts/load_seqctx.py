"""Generic targeted loader for a species' sequence-context layer into grn.sqlite3 —
no full rebuild. Replaces load_arabidopsis_seqctx.py. Idempotent: clears the species'
existing rows first. Loads whatever caches are present:
  gene_id_crosswalk_<species>.json.gz , gene_windows_<species>.json.gz   (always)
  motifs_<species>.json , motif_hits_<species>.json.gz                   (if non-empty)

Run once before scanning (crosswalk + windows) and again after (motifs + hits).

Usage: python backend/scripts/load_seqctx.py <species>
"""
import gzip
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import species_config  # noqa: E402

DATA = Path(__file__).parent.parent / "data"
DB = DATA / "grn.sqlite3"


def _load(path):
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def main(species):
    cfg = species_config.get(species)
    if not cfg:
        sys.exit(f"unknown species '{species}'")
    assembly = cfg["assembly"]
    conn = sqlite3.connect(DB)

    cw = _load(DATA / f"gene_id_crosswalk_{species}.json.gz")
    win = _load(DATA / f"gene_windows_{species}.json.gz")
    conn.execute("DELETE FROM gene_id_crosswalk WHERE species=?", (species,))
    conn.executemany(
        "INSERT OR REPLACE INTO gene_id_crosswalk "
        "(species, atlas_gene_id, ext_gene_id, ext_assembly, relation) VALUES (?,?,?,?,?)",
        [(r["species"], r["atlas_gene_id"], r["ext_gene_id"], r["ext_assembly"], r["relation"]) for r in cw])
    conn.execute("DELETE FROM gene_windows WHERE assembly=?", (assembly,))
    conn.executemany(
        "INSERT OR REPLACE INTO gene_windows "
        "(ext_gene_id, assembly, window_type, chromosome, start, end, strand) VALUES (?,?,?,?,?,?,?)",
        [(r["ext_gene_id"], r["assembly"], r["window_type"], r["chromosome"],
          r["start"], r["end"], r["strand"]) for r in win])
    print(f"loaded crosswalk={len(cw)} windows={len(win)}")

    motifs = _load(DATA / f"motifs_{species}.json")
    hits = _load(DATA / f"motif_hits_{species}.json.gz")
    if motifs:
        conn.execute("DELETE FROM motifs WHERE tf_gene_id IN (SELECT id FROM genes WHERE species=?)",
                     (species,))
        conn.executemany(
            "INSERT OR REPLACE INTO motifs (motif_id, source, jaspar_id, tf_gene_id, tf_symbol) "
            "VALUES (?,?,?,?,?)",
            [(m["motif_id"], m["source"], m.get("jaspar_id"), m.get("tf_gene_id"), m.get("tf_symbol"))
             for m in motifs])
    if hits:
        conn.execute("DELETE FROM motif_hits WHERE assembly=?", (assembly,))
        conn.executemany(
            "INSERT INTO motif_hits (ext_gene_id, motif_id, assembly, window_type, chromosome, "
            "start, end, strand, score, p_value, tier, site_confidence) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(h["ext_gene_id"], h["motif_id"], h["assembly"], h["window_type"], h["chromosome"],
              h["start"], h["end"], h["strand"], h["score"], h["p_value"], h["tier"], h["site_confidence"])
             for h in hits])
    print(f"loaded motifs={len(motifs)} hits={len(hits)}")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: load_seqctx.py <species>")
    main(sys.argv[1])
