#!/usr/bin/env python3
"""Measure feedback changes attributable to cross-species transfer candidates."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
import feedback_control  # noqa: E402

DB = ROOT / "backend" / "data" / "grn.sqlite3"
REPORT = ROOT / "docs" / "benchmarks" / "cross-species-feedback-impact.json"
BASELINE = ROOT / "docs" / "benchmarks" / "cross-species-transfer-baseline.json"
SOURCE = "Conserved signed orthology"


def metrics(conn: sqlite3.Connection, species: str, exploratory: bool) -> dict:
    result = feedback_control.analyze_feedback(
        conn, species, feedback_control.FeedbackParameters(
            min_confidence=0.4 if exploratory else 0.5,
            include_candidates=True, include_exploratory=exploratory,
            discover_systems=False, probabilistic_samples=0,
        ),
    )
    return {"graph_edges": result["graph"]["edges"],
            "feedback_cores": result["summary"]["feedback_cores"],
            "feedback_genes": result["summary"]["feedback_genes"],
            "feedback_edges": result["summary"]["feedback_edges"],
            "macro_circuits": result["summary"]["macro_circuits"]}


def benchmark(conn: sqlite3.Connection) -> dict:
    species_list = [row[0] for row in conn.execute(
        "SELECT DISTINCT species FROM regulatory_edge_candidates "
        "WHERE evidence_sources LIKE ? ORDER BY species", (f'%\"{SOURCE}\"%',)
    )]
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "ablated_source": SOURCE, "species": {},
              "projection_summary": {
                  row[0]: int(row[1]) for row in conn.execute(
                      "SELECT status,COUNT(*) FROM orthology_transfer_candidates GROUP BY status"
                  )
              },
              "interpretation": "Observed interactions are unchanged; deltas isolate transfer candidates."}
    for species in species_list:
        with_source = {mode: metrics(conn, species, mode == "exploratory")
                       for mode in ("supported", "exploratory")}
        conn.execute("SAVEPOINT transfer_ablation")
        try:
            conn.execute(
                "DELETE FROM regulatory_edge_candidates WHERE species=? AND evidence_sources LIKE ?",
                (species, f'%\"{SOURCE}\"%'),
            )
            without = {mode: metrics(conn, species, mode == "exploratory")
                       for mode in ("supported", "exploratory")}
        finally:
            conn.execute("ROLLBACK TO transfer_ablation")
            conn.execute("RELEASE transfer_ablation")
        report["species"][species] = {
            mode: {"with_transfer": with_source[mode], "without_transfer": without[mode],
                   "delta": {key: with_source[mode][key] - without[mode][key]
                             for key in with_source[mode]}}
            for mode in ("supported", "exploratory")
        }
    report["known_circuit_impact"] = {
        "supported_graph_changed": any(
            any(value != 0 for value in modes["supported"]["delta"].values())
            for modes in report["species"].values()
        ),
        "interpretation": (
            "Known-circuit recovery cannot regress when the supported graph is unchanged; "
            "exploratory additions are reported separately and are not counted as recovery."
        ),
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
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    baseline = {
        "generated_at": report["generated_at"],
        "definition": "Feedback metrics with cross-species transfer candidates ablated",
        "species": {species: {mode: values["without_transfer"] for mode, values in modes.items()}
                    for species, modes in report["species"].items()},
    }
    BASELINE.write_text(json.dumps(baseline, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
