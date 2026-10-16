#!/usr/bin/env python3
"""Measure feedback structure attributable to perturbation-consensus candidates."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import feedback_control  # noqa: E402


DB = BACKEND / "data" / "grn.sqlite3"
REPORT = ROOT / "docs" / "benchmarks" / "perturbation-feedback-ablation.json"
SOURCE = "Perturbation sign consensus"


def metrics(conn: sqlite3.Connection, species: str, exploratory: bool) -> dict:
    result = feedback_control.analyze_feedback(
        conn,
        species,
        feedback_control.FeedbackParameters(
            min_confidence=0.4 if exploratory else 0.5,
            include_candidates=True,
            include_exploratory=exploratory,
            discover_systems=False,
            probabilistic_samples=0,
        ),
    )
    return {
        "graph_edges": result["graph"]["edges"],
        "feedback_cores": result["summary"]["feedback_cores"],
        "feedback_genes": result["summary"]["feedback_genes"],
        "feedback_edges": result["summary"]["feedback_edges"],
        "macro_circuits": result["summary"]["macro_circuits"],
    }


def delta(with_source: dict, without_source: dict) -> dict:
    return {key: with_source[key] - without_source[key] for key in with_source}


def benchmark(conn: sqlite3.Connection) -> dict:
    species_list = [
        row[0] for row in conn.execute(
            "SELECT DISTINCT species FROM regulatory_edge_candidates "
            "WHERE evidence_sources LIKE ? ORDER BY species", (f'%"{SOURCE}"%',)
        )
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ablated_source": SOURCE,
        "species": {},
        "interpretation": (
            "Deltas compare the same database and algorithm with versus without candidates "
            "that depend on perturbation consensus. Observed interactions are untouched."
        ),
    }
    for species in species_list:
        with_source = {
            "supported": metrics(conn, species, False),
            "exploratory": metrics(conn, species, True),
        }
        conn.execute("SAVEPOINT perturbation_ablation")
        try:
            conn.execute(
                "DELETE FROM regulatory_edge_candidates WHERE species=? AND evidence_sources LIKE ?",
                (species, f'%"{SOURCE}"%'),
            )
            without_source = {
                "supported": metrics(conn, species, False),
                "exploratory": metrics(conn, species, True),
            }
        finally:
            conn.execute("ROLLBACK TO perturbation_ablation")
            conn.execute("RELEASE perturbation_ablation")
        report["species"][species] = {
            mode: {
                "with_source": with_source[mode],
                "without_source": without_source[mode],
                "delta": delta(with_source[mode], without_source[mode]),
            }
            for mode in ("supported", "exploratory")
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        report = benchmark(conn)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
