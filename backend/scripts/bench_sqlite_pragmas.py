#!/usr/bin/env python3
"""Would raising SQLite's page cache fix the perturbation timeouts?

The API connection sets no pragmas, so a 9 GB database is served with the
stock 2 MB page cache. This A/B/A-tests that against a tuned connection on a
cascade-shaped workload. The third pass repeats the default so an apparent win
cannot be OS page-cache warming.

Reads only; changes no data and no file.

    backend/venv/bin/python backend/scripts/bench_sqlite_pragmas.py
"""
import sqlite3
import time
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "backend/data/grn.sqlite3"
FANOUT = ("SELECT g.*, i.regulation_type, i.confidence, i.sources, i.pmids, "
          "i.sign, i.sign_evidence, i.sign_r FROM interactions i "
          "JOIN genes g ON g.id = i.target_id "
          "WHERE i.source_id = ? AND i.confidence >= ?")
TUNED = ("PRAGMA cache_size = -262144",      # 256 MB instead of 2 MB
         "PRAGMA mmap_size = 1073741824",    # 1 GB
         "PRAGMA temp_store = MEMORY")


def seeds(n=400):
    """High fan-out genes: the shape a cascade actually walks."""
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = [r[0] for r in conn.execute(
        "SELECT source_id FROM interactions GROUP BY source_id "
        "ORDER BY COUNT(*) DESC LIMIT ?", (n,))]
    conn.close()
    return rows


def run(genes, tuned, label):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    if tuned:
        for p in TUNED:
            conn.execute(p)
    cache = conn.execute("PRAGMA cache_size").fetchone()[0]
    mm = conn.execute("PRAGMA mmap_size").fetchone()[0]
    t0 = time.perf_counter()
    rows = 0
    for g in genes:
        rows += len(conn.execute(FANOUT, (g, 0.0)).fetchall())
    el = time.perf_counter() - t0
    conn.close()
    print(f"  {label:26} {el:7.2f}s for {len(genes)} reads "
          f"({el/len(genes)*1000:6.1f} ms each, {rows:,} rows)")
    print(f"  {'':26} cache_size={cache} mmap_size={mm/1e9:.0f}GB")
    return el


def main():
    genes = seeds()
    print("=" * 72)
    print(f"workload: {len(genes)} fan-out reads over the highest-degree genes\n")
    a1 = run(genes, False, "A  default (2 MB cache)")
    b = run(genes, True, "B  tuned (256 MB + mmap)")
    a2 = run(genes, False, "A' default again")
    print("-" * 72)
    print(f"  tuned vs first default:  {a1/b:5.2f}x faster")
    print(f"  tuned vs second default: {a2/b:5.2f}x faster")
    warm = (a1 - a2) / a1 * 100 if a1 else 0
    print(f"  default improved {warm:.0f}% on repeat -> that much was OS cache warming")
    if a2 / b > 1.3:
        print(f"\n  -> the pragmas are a real win. At {a2/b:.1f}x, a 156 s "
              f"perturbation run would land near {156*b/a2:.0f} s.")
    else:
        print("\n  -> not a page-cache problem. The cost is elsewhere; do not "
              "change the pragmas on this evidence.")
    print("=" * 72)


if __name__ == "__main__":
    main()
