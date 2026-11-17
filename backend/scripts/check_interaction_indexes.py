#!/usr/bin/env python3
"""Is the 20 ms fan-out read avoidable? Indexes and query plan.

    backend/venv/bin/python backend/scripts/check_interaction_indexes.py
"""
import sqlite3
import time
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "backend/data/grn.sqlite3"
FANOUT = ("SELECT g.*, i.regulation_type, i.confidence, i.sources, i.pmids, "
          "i.sign, i.sign_evidence, i.sign_r FROM interactions i "
          "JOIN genes g ON g.id = i.target_id "
          "WHERE i.source_id = ? AND i.confidence >= ?")


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    print("=" * 70)
    print("indexes on interactions:")
    for _, name, *_ in conn.execute("PRAGMA index_list(interactions)"):
        cols = [r[2] for r in conn.execute(f"PRAGMA index_info('{name}')")]
        print(f"   {name:42} ({', '.join(cols)})")
    print("\nindexes on genes:")
    for _, name, *_ in conn.execute("PRAGMA index_list(genes)"):
        cols = [r[2] for r in conn.execute(f"PRAGMA index_info('{name}')")]
        print(f"   {name:42} ({', '.join(cols)})")

    print("-" * 70)
    print("query plan for one fan-out read:")
    for row in conn.execute("EXPLAIN QUERY PLAN " + FANOUT, ("TP53", 0.0)):
        print(f"   {row[-1]}")

    print("-" * 70)
    # Split the cost: the interactions scan alone, then the join.
    bare = ("SELECT i.target_id, i.confidence FROM interactions i "
            "WHERE i.source_id = ? AND i.confidence >= ?")
    for label, sql in (("interactions only", bare), ("with genes join", FANOUT)):
        t0 = time.perf_counter()
        for _ in range(5):
            n = len(conn.execute(sql, ("TP53", 0.0)).fetchall())
        print(f"   {label:20} {(time.perf_counter()-t0)/5*1000:7.1f} ms  ({n:,} rows)")

    # Does a cold-ish cache matter, or is this steady state?
    print("-" * 70)
    print("page cache / journal state:")
    for p in ("journal_mode", "cache_size", "page_size", "wal_autocheckpoint"):
        print(f"   {p:20} {conn.execute(f'PRAGMA {p}').fetchone()[0]}")
    conn.close()
    print("=" * 70)


if __name__ == "__main__":
    main()
