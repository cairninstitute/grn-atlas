#!/usr/bin/env python3
"""Move projected plant signs onto the tier that already exists for them.

CROSS_SPECIES_SIGN_TRANSFER.md states that transfers "are stored as evidence
candidates and never modify the observed interaction graph". The database
partly agrees with itself: 1,526 edges already carry sign_evidence =
'ortholog_transfer', and because the default tiers are ('measured',
'perturbation') those are correctly excluded from the observed graph.

But 3,964 edges sourced only from `Inferred:*` projections still carry
sign_evidence = 'measured'. Their signs are Arabidopsis signs copied across an
ortholog mapping; nothing in the recipient species measured them. Every
feedback loop reported for tomato, petunia, rice and pepper rests on these.

This moves them to the tier the project already defined for exactly this case.
No new tier, no query change - the same mechanism that already holds the other
1,526 out.

Edges carrying a native source alongside the projection are reported but left
alone by default: a sign there may have a local basis. --include-mixed moves
them too.

--revert reads the report and restores only the rows this script moved, so the
edges that were already on the transfer tier are not disturbed.

Usage:
    venv/bin/python backend/scripts/migrate_projected_signs.py            # dry run
    venv/bin/python backend/scripts/migrate_projected_signs.py --apply
    venv/bin/python backend/scripts/migrate_projected_signs.py --revert
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
REPORT = BACKEND / "data" / "projected_sign_migration.json"

FROM_TIER = "measured"
TO_TIER = "ortholog_transfer"
PROJECTION_PREFIX = "Inferred:"


def classify(conn: sqlite3.Connection) -> tuple[list, list, Counter]:
    """Split projected signed edges into projection-only and mixed-source."""
    only, mixed, stats = [], [], Counter()
    for sid, tid, species, raw, sign in conn.execute(
            "SELECT i.source_id, i.target_id, g.species, i.sources, i.sign "
            "FROM interactions i, genes g "
            "WHERE g.id = i.source_id AND i.sign IS NOT NULL "
            "AND i.sign_evidence = ? AND i.sources LIKE ?",
            (FROM_TIER, f"%{PROJECTION_PREFIX}%")):
        try:
            sources = json.loads(raw or "[]")
        except (TypeError, ValueError):
            stats["unparseable_sources"] += 1
            continue
        if not any(str(s).startswith(PROJECTION_PREFIX) for s in sources):
            continue
        row = {"source_id": sid, "target_id": tid, "species": species,
               "sign": sign, "sources": sources}
        if all(str(s).startswith(PROJECTION_PREFIX) for s in sources):
            only.append(row)
            stats[f"{species}:projection_only"] += 1
        else:
            mixed.append(row)
            stats[f"{species}:mixed"] += 1
    return only, mixed, stats


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--include-mixed", action="store_true",
                    help="also move edges that carry a native source")
    ap.add_argument("--revert", action="store_true",
                    help="restore exactly the rows the last --apply moved")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"database missing: {args.db}", file=sys.stderr)
        return 1

    writing = args.apply or args.revert
    conn = sqlite3.connect(f"file:{args.db}?mode={'rw' if writing else 'ro'}", uri=True)

    if args.revert:
        if not args.report.exists():
            print(f"no report at {args.report}; nothing to revert", file=sys.stderr)
            return 1
        moved = json.loads(args.report.read_text()).get("moved", [])
        conn.execute("BEGIN")
        n = 0
        for r in moved:
            n += conn.execute(
                "UPDATE interactions SET sign_evidence=? "
                "WHERE source_id=? AND target_id=? AND sign_evidence=?",
                (FROM_TIER, r["source_id"], r["target_id"], TO_TIER)).rowcount
        conn.commit()
        print(f"restored {n:,} of {len(moved):,} rows to '{FROM_TIER}'")
        return 0

    only, mixed, stats = classify(conn)
    moving = only + (mixed if args.include_mixed else [])

    by_species = Counter(r["species"] for r in moving)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(args.db.resolve()),
        "from_tier": FROM_TIER, "to_tier": TO_TIER,
        "include_mixed": args.include_mixed,
        "counts": dict(stats),
        "projection_only": len(only), "mixed_source": len(mixed),
        "moved": moving if args.apply else [],
        "would_move": [] if args.apply else moving,
        "mixed_examples": mixed[:20],
    }

    print(f"\n{'APPLYING' if args.apply else 'DRY RUN - nothing written'}\n")
    print("  projection-only signed edges (moving):")
    for sp, n in sorted(by_species.items(), key=lambda x: -x[1]):
        print(f"    {sp:<12}{n:>8,}")
    print(f"\n  total moving:        {len(moving):,}")
    print(f"  mixed-source edges:  {len(mixed):,}"
          f"{'  (included)' if args.include_mixed else '  (left alone)'}")
    if mixed and not args.include_mixed:
        seen = Counter(tuple(sorted(r["sources"])) for r in mixed)
        print("    their source combinations:")
        for combo, n in seen.most_common(6):
            print(f"      {n:>5,}  {list(combo)}")

    if args.apply:
        conn.execute("BEGIN")
        n = 0
        for r in moving:
            n += conn.execute(
                "UPDATE interactions SET sign_evidence=? "
                "WHERE source_id=? AND target_id=? AND sign_evidence=?",
                (TO_TIER, r["source_id"], r["target_id"], FROM_TIER)).rowcount
        conn.commit()
        print(f"\nApplied: {n:,} rows moved to '{TO_TIER}'.")
        print("Re-run the content digest, then feedback control for the plant "
              "species - their observed cores should go to near zero, which is "
              "the honest state for a projected network.")
        print("--revert restores exactly these rows.")
    else:
        print("\n  Re-run with --apply to perform it. Take a content digest first.")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"  Report: {args.report}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
