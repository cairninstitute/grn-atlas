#!/usr/bin/env python3
"""Did the Phase 1 migrations cause the three data-driven test failures?

    backend/venv/bin/python backend/scripts/triage_phase1_test_failures.py
"""
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend/data/grn.sqlite3"
ARA = ["AT5G04760", "AT1G01780", "AT1G03360", "AT1G07830",
       "AT1G09800", "AT1G10360", "AT1G13550"]
OBSERVED = ("('measured','perturbation')", 0.5)


def skill(name, args):
    r = subprocess.run([sys.executable, str(ROOT / ".agents/skills" / name /
                                           "scripts/run.py"), *args],
                       capture_output=True, text=True, cwd=ROOT, timeout=180)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"_error": (r.stderr or r.stdout).strip()[-200:]}


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    print("=" * 70)
    print("1. grn-pathfinding TP53->BAX : do the edges still exist?")
    for a, b in [("TP53", "BAX"), ("TP53", "MYC"), ("MYC", "BAX")]:
        row = conn.execute(
            "SELECT sign, sign_evidence, confidence, sources FROM interactions "
            "WHERE source_id=? AND target_id=?", (a, b)).fetchone()
        if not row:
            print(f"   {a:6}->{b:6} ABSENT from interactions")
            continue
        sign, ev, conf, src = row
        inobs = ev in ("measured", "perturbation") and (conf or 0) >= 0.5
        print(f"   {a:6}->{b:6} sign={str(sign):10} tier={ev:26} "
              f"conf={conf} observed={inobs}")
        print(f"                 sources={(src or '')[:70]}")
    p = skill("grn-pathfinding", ["--source", "TP53", "--target", "BAX",
                                  "--max-depth", "2"])
    n = len(p.get("paths", []))
    print(f"   -> skill returns {n} path(s)"
          + (f"   keys={sorted(p)[:6]}" if n == 0 else ""))
    if n == 0 and "error" in p:
        print(f"      error: {str(p['error'])[:120]}")

    print("-" * 70)
    print("2. grn-dynamics arabidopsis module : did 1C remove its signs?")
    q = ",".join("?" for _ in ARA)
    total = conn.execute(
        f"SELECT COUNT(*) FROM interactions WHERE source_id IN ({q}) "
        f"AND target_id IN ({q})", ARA + ARA).fetchone()[0]
    tiers = Counter()
    for (ev,) in conn.execute(
            f"SELECT sign_evidence FROM interactions WHERE source_id IN ({q}) "
            f"AND target_id IN ({q}) AND sign IS NOT NULL", ARA + ARA):
        tiers[ev] += 1
    obs = conn.execute(
        f"SELECT COUNT(*) FROM interactions WHERE source_id IN ({q}) "
        f"AND target_id IN ({q}) AND sign IS NOT NULL "
        f"AND sign_evidence IN {OBSERVED[0]} AND confidence >= ?",
        ARA + ARA + [OBSERVED[1]]).fetchone()[0]
    print(f"   edges among the 7 genes: {total}")
    print(f"   signed, by tier: {dict(tiers) or '(none)'}")
    print(f"   in the observed graph: {obs}   <- the test needs >= 1")
    if tiers.get("perturbation_exploratory"):
        print(f"   -> {tiers['perturbation_exploratory']} sign(s) were gated out "
              f"by 1C; that is why the test fails")

    print("-" * 70)
    print("3. signed totals by tier (context)")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(interactions)")}
    if "species" in cols:
        for sp in ("arabidopsis", "human"):
            t = conn.execute("SELECT COUNT(*) FROM interactions WHERE species=? "
                             "AND sign IS NOT NULL", (sp,)).fetchone()[0]
            o = conn.execute(f"SELECT COUNT(*) FROM interactions WHERE species=? "
                             f"AND sign IS NOT NULL AND sign_evidence IN "
                             f"{OBSERVED[0]} AND confidence >= ?",
                             (sp, OBSERVED[1])).fetchone()[0]
            print(f"   {sp:12} signed={t:>7,}  observed={o:>7,}")
    else:
        print("   (interactions has no species column; tiers overall instead)")
        for ev, n in conn.execute(
                "SELECT sign_evidence, COUNT(*) FROM interactions "
                "WHERE sign IS NOT NULL GROUP BY sign_evidence ORDER BY 2 DESC"):
            print(f"   {str(ev):28} {n:>8,}")
    conn.close()
    print("=" * 70)


if __name__ == "__main__":
    main()
