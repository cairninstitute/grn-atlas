"""Promote curated UniProt symbols into genes.symbol (real names replace loci) — no
full rebuild. Only fills genes that currently lack a native symbol (symbol == id), so
existing curated symbols (e.g. AN2) are never clobbered. Records provenance in a new
`symbol_source` column.

Usage: python backend/scripts/load_curated_symbols.py <species>
"""
import json
import sqlite3
import sys
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
DB = DATA / "grn.sqlite3"


def main(species):
    path = DATA / f"curated_symbols_{species}.json"
    if not path.exists():
        sys.exit(f"missing {path}")
    curated = json.loads(path.read_text())
    conn = sqlite3.connect(DB)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(genes)")]
    if "symbol_source" not in cols:
        conn.execute("ALTER TABLE genes ADD COLUMN symbol_source TEXT")

    n = 0
    for gid, info in curated.items():
        cur = conn.execute("UPDATE genes SET symbol=?, symbol_source=? "
                           "WHERE id=? AND species=? AND symbol=id",
                           (info["symbol"], info["source"], gid, species))
        n += cur.rowcount
    conn.commit()
    conn.close()
    print(f"{species}: promoted {n} curated symbols (of {len(curated)} available)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: load_curated_symbols.py <species>")
    main(sys.argv[1])
