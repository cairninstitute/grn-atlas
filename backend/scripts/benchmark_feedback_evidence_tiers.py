#!/usr/bin/env python3
"""Benchmark observed, supported, exploratory, and multilayer feedback views."""

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
import feedback_control  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=BACKEND / "data" / "grn.sqlite3")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs" / "benchmarks" / "feedback-evidence-tiers.json")
    parser.add_argument("--samples", type=int, default=24)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        species = [row[0] for row in conn.execute(
            "SELECT DISTINCT species FROM regulatory_edge_candidates ORDER BY species"
        )]
        result = {"generated_at": datetime.now(timezone.utc).isoformat(), "species": {}}
        for name in species:
            modes = {}
            for mode, kwargs in (
                ("observed", {}),
                ("supported", {"include_candidates": True}),
                ("exploratory", {"include_candidates": True, "include_exploratory": True,
                                 "probabilistic_samples": args.samples}),
                ("multilayer", {"include_candidates": True, "include_exploratory": True,
                                "include_multilayer": True}),
            ):
                start = time.perf_counter()
                analysis = feedback_control.analyze_feedback(
                    conn, name, feedback_control.FeedbackParameters(
                        min_confidence=0.4 if mode in ("exploratory", "multilayer") else 0.5,
                        discover_systems=False, max_cores=1, max_circuits=1,
                        circuits_per_core=1, max_search_states=1_000,
                        max_controllers=1, **kwargs,
                    ),
                )
                modes[mode] = {
                    "feedback_cores": analysis["summary"]["feedback_cores"],
                    "feedback_genes": analysis["summary"]["feedback_genes"],
                    "feedback_edges": analysis["summary"]["feedback_edges"],
                    "macro_circuits": analysis["summary"]["macro_circuits"],
                    "graph_edges": analysis["graph"]["edges"],
                    "seconds": round(time.perf_counter() - start, 3),
                    "probabilistic_members": len(
                        analysis["probabilistic_core_membership"]["memberships"]
                    ),
                }
            impact = conn.execute(
                "SELECT COUNT(*),COALESCE(SUM(closes_cycle),0),"
                "COALESCE(SUM(CASE WHEN closes_cycle=1 THEN feedback_nodes_added ELSE 0 END),0) "
                "FROM regulatory_candidate_impacts WHERE species=?", (name,),
            ).fetchone()
            result["species"][name] = {
                "modes": modes,
                "candidate_impact": {"ranked": impact[0], "cycle_closing": impact[1],
                                     "potential_feedback_nodes_across_candidates": impact[2]},
            }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
