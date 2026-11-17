#!/usr/bin/env python3
"""How long does grn-perturbation actually take, and why?

The suite's timeout is 120 s. A case at ~130 s is long-standing fragility that
flips between runs; one at ~400 s is something materially slower. This measures
it instead of inferring it.

    backend/venv/bin/python backend/scripts/time_perturbation.py
"""
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend/data/grn.sqlite3"
RUNNER = ROOT / ".agents/skills/grn-perturbation/scripts/run.py"
CAP = 240


def main():
    print("=" * 66)
    for name in ("grn.sqlite3-wal", "grn.sqlite3-shm"):
        p = DB.parent / name
        print(f"  {name:18} {p.stat().st_size/1e6:,.1f} MB" if p.exists()
              else f"  {name:18} absent")

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    deg = conn.execute("SELECT COUNT(*) FROM interactions WHERE source_id='TP53'"
                       ).fetchone()[0]
    print(f"  TP53 out-degree    {deg:,} interactions")

    # Isolate the accessor: how long does one fan-out read cost?
    sql = ("SELECT g.*, i.regulation_type, i.confidence, i.sources, i.pmids, "
           "i.sign, i.sign_evidence, i.sign_r FROM interactions i "
           "JOIN genes g ON g.id = i.target_id "
           "WHERE i.source_id = ? AND i.confidence >= ?")
    t0 = time.perf_counter()
    for _ in range(5):
        conn.execute(sql, ("TP53", 0.0)).fetchall()
    per = (time.perf_counter() - t0) / 5
    print(f"  one TP53 fan-out read  {per*1000:,.1f} ms")
    conn.close()

    print("-" * 66)
    print(f"  running: grn-perturbation --gene-id TP53 --action ko  (cap {CAP}s)")
    for attempt in (1, 2):
        t0 = time.perf_counter()
        try:
            r = subprocess.run([sys.executable, str(RUNNER), "--gene-id", "TP53",
                                "--action", "ko"], capture_output=True, text=True,
                               cwd=ROOT, timeout=CAP)
            el = time.perf_counter() - t0
            tag = "OK" if r.returncode == 0 else f"exit {r.returncode}"
            verdict = ("under the 120s suite timeout" if el < 120
                       else "OVER the 120s suite timeout")
            print(f"    run {attempt}: {el:7.1f}s  {tag}  -> {verdict}")
            if r.returncode != 0:
                print(f"       stderr: {r.stderr.strip()[-160:]}")
        except subprocess.TimeoutExpired:
            print(f"    run {attempt}: >{CAP}s  killed -- not borderline, "
                  f"materially slower")
            break
    print("=" * 66)


if __name__ == "__main__":
    main()
