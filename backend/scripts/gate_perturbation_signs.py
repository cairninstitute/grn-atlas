#!/usr/bin/env python3
"""Hold perturbation-derived signs to the calibration gate they were measured against.

calibrate_perturbation_signs.py evaluates each species and sign class separately
and records the outcome in `perturbation_sign_calibration.gate_pass`. One class
passes: human activation, at 87.5% precision over 1,497 cases. Human repression
scored 21.2%. Both Arabidopsis classes failed on 49 and 8 cases.

The observed graph does not consult that table. feedback_control.py admits any
row whose sign_evidence is in the default tiers, so every failed class is in the
graph on the same footing as the one that passed.

This moves the failed classes to a distinct tier, `perturbation_exploratory`.
Because the default tiers are ('measured','perturbation'), the renamed rows drop
out of the observed graph with no query change - the same mechanism that already
keeps `ortholog_transfer` out.

Trade-off, stated plainly: the exploratory views in feedback_control.py are fed
by `regulatory_edge_candidates`, not by interaction tiers, so these edges become
invisible everywhere rather than demoted. That matches how `ortholog_transfer`
already behaves. Surfacing them under --include-exploratory is a follow-up, not
part of this change.

Read-only unless --apply is given.

Usage:
    venv/bin/python backend/scripts/gate_perturbation_signs.py            # dry run
    venv/bin/python backend/scripts/gate_perturbation_signs.py --apply
    venv/bin/python backend/scripts/gate_perturbation_signs.py --verify
    venv/bin/python backend/scripts/gate_perturbation_signs.py --revert   # undo
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
REPORT = BACKEND / "data" / "perturbation_gating_report.json"

GATED_TIER = "perturbation"
UNGATED_TIER = "perturbation_exploratory"


def gate_status(conn: sqlite3.Connection) -> dict[tuple[str, str], dict]:
    out = {}
    for species, rel, cases, precision, passed in conn.execute(
            "SELECT species, relation_type, cases, precision, gate_pass "
            "FROM perturbation_sign_calibration"):
        out[(species, rel)] = {"cases": cases, "precision": precision,
                               "gate_pass": bool(passed)}
    return out


def survey(conn: sqlite3.Connection, tier: str) -> list[dict]:
    return [{"species": s, "relation_type": r, "edges": n} for s, r, n in conn.execute(
        "SELECT g.species, i.sign, COUNT(*) FROM interactions i, genes g "
        "WHERE g.id = i.source_id AND i.sign_evidence = ? AND i.sign IS NOT NULL "
        "GROUP BY g.species, i.sign ORDER BY COUNT(*) DESC", (tier,))]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true",
                    help="report the current tier split against the gate table")
    ap.add_argument("--revert", action="store_true",
                    help="move perturbation_exploratory rows back to perturbation")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"database missing: {args.db}", file=sys.stderr)
        return 1

    writing = args.apply or args.revert
    conn = sqlite3.connect(f"file:{args.db}?mode={'rw' if writing else 'ro'}", uri=True)
    gates = gate_status(conn)
    if not gates:
        print("perturbation_sign_calibration is empty; run "
              "backend/scripts/calibrate_perturbation_signs.py first", file=sys.stderr)
        return 1

    if args.revert:
        n = conn.execute("UPDATE interactions SET sign_evidence=? WHERE sign_evidence=?",
                         (GATED_TIER, UNGATED_TIER)).rowcount
        conn.commit()
        print(f"moved {n:,} rows back to '{GATED_TIER}'")
        return 0

    if args.verify:
        print(f"\ncalibration gate ({len(gates)} classes)")
        for (sp, rel), g in sorted(gates.items()):
            mark = "PASS" if g["gate_pass"] else "FAIL"
            print(f"  {mark}  {sp:<12} {rel:<11} {g['cases']:>6,} cases  "
                  f"precision {g['precision']:.3f}")
        for tier in (GATED_TIER, UNGATED_TIER):
            rows = survey(conn, tier)
            print(f"\n{tier}: {sum(r['edges'] for r in rows):,} edges")
            for r in rows:
                g = gates.get((r["species"], r["relation_type"]))
                state = "ungated" if (g and not g["gate_pass"]) else (
                    "gated" if g else "no calibration record")
                print(f"  {r['species']:<12} {r['relation_type']:<11} "
                      f"{r['edges']:>8,}   {state}")
        return 0

    # Plan: which classes currently in the gated tier failed their gate.
    current = survey(conn, GATED_TIER)
    move, keep, unknown = [], [], []
    for r in current:
        g = gates.get((r["species"], r["relation_type"]))
        if g is None:
            unknown.append(r)
        elif g["gate_pass"]:
            keep.append(r)
        else:
            move.append({**r, "precision": g["precision"], "cases": g["cases"]})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(args.db.resolve()),
        "gated_tier": GATED_TIER, "ungated_tier": UNGATED_TIER,
        "classes_passing": keep, "classes_failing": move,
        "classes_without_calibration": unknown,
        "edges_to_move": sum(r["edges"] for r in move),
        "edges_retained": sum(r["edges"] for r in keep),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")

    print(f"\n{'APPLYING' if args.apply else 'DRY RUN - nothing written'}\n")
    print("  retained in the observed graph (gate passed):")
    for r in keep:
        print(f"    {r['species']:<12} {r['relation_type']:<11} {r['edges']:>8,}")
    print("\n  moving out of the observed graph (gate failed):")
    for r in move:
        print(f"    {r['species']:<12} {r['relation_type']:<11} {r['edges']:>8,}"
              f"   precision {r['precision']:.3f} over {r['cases']:,} cases")
    if unknown:
        print("\n  no calibration record - left alone, decide explicitly:")
        for r in unknown:
            print(f"    {r['species']:<12} {r['relation_type']:<11} {r['edges']:>8,}")
    print(f"\n  total moving: {report['edges_to_move']:,}   "
          f"retained: {report['edges_retained']:,}")
    print(f"  Report: {args.report}")

    if args.apply:
        conn.execute("BEGIN")
        try:
            moved = 0
            for r in move:
                moved += conn.execute(
                    "UPDATE interactions SET sign_evidence=? "
                    "WHERE sign_evidence=? AND sign=? AND source_id IN "
                    "(SELECT id FROM genes WHERE species=?)",
                    (UNGATED_TIER, GATED_TIER, r["relation_type"], r["species"])).rowcount
            conn.commit()
            print(f"\nApplied: {moved:,} rows moved to '{UNGATED_TIER}'.")
            print("Re-run the content digest, then audit_evidence_tiers.py - it "
                  "should now report no ungated classes.")
            print("--revert undoes this exactly.")
        except Exception:
            conn.rollback()
            raise
    else:
        print("\n  Re-run with --apply to perform it. Take a content digest first.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
