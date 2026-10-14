#!/usr/bin/env python3
"""Generate source-level mapping, novelty, conflict, and feedback-gain metrics."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import feedback_control  # noqa: E402
from external_evidence import benchmark_source, ensure_schema  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
OUT = BACKEND / "data" / "regulatory_source_qualification.json"


def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def qualify(conn: sqlite3.Connection) -> dict:
    ensure_schema(conn)
    sources = [row[0] for row in conn.execute("SELECT DISTINCT source_name FROM regulatory_evidence ORDER BY source_name")]
    reports = []
    for source in sources:
        report = benchmark_source(conn, source)
        layers = dict(conn.execute(
            "SELECT evidence_layer,COUNT(*) FROM regulatory_evidence WHERE source_name=? GROUP BY evidence_layer",
            (source,),
        ))
        run = conn.execute(
            "SELECT source_version,source_url,fetched_at,sha256,status,counts FROM source_import_runs "
            "WHERE source_name=? ORDER BY import_run_id DESC LIMIT 1", (source,),
        ).fetchone()
        report["evidence_layers"] = layers
        if run:
            report["import"] = {"version": run[0], "url": run[1], "fetched_at": run[2],
                                "sha256": run[3], "status": run[4], "counts": json.loads(run[5])}
            input_count = report["import"]["counts"].get("input") or report["import"]["counts"].get("input_targets")
            if input_count:
                report["mapping_rate"] = round(report["mapped_records"] / input_count, 4)
        reports.append(report)

    species_reports = {}
    has_candidates = table_exists(conn, "regulatory_edge_candidates")
    for species, in conn.execute("SELECT DISTINCT species FROM genes ORDER BY species"):
        observed = feedback_control.analyze_feedback(conn, species, feedback_control.FeedbackParameters(
            max_cores=200, max_circuits=1, circuits_per_core=1, discover_systems=False,
        ))
        completed = observed
        if has_candidates:
            completed = feedback_control.analyze_feedback(conn, species, feedback_control.FeedbackParameters(
                max_cores=200, max_circuits=1, circuits_per_core=1, discover_systems=False,
                include_candidates=True,
            ))
        candidate_count = conn.execute(
            "SELECT COUNT(*) FROM regulatory_edge_candidates WHERE species=? AND status='candidate'",
            (species,),
        ).fetchone()[0] if has_candidates else 0
        species_reports[species] = {
            "candidate_edges": candidate_count,
            "observed_feedback_cores": observed["summary"]["feedback_cores"],
            "completed_feedback_cores": completed["summary"]["feedback_cores"],
            "observed_feedback_genes": observed["summary"]["feedback_genes"],
            "completed_feedback_genes": completed["summary"]["feedback_genes"],
            "feedback_core_delta": (
                completed["summary"]["feedback_cores"] - observed["summary"]["feedback_cores"]
            ),
            "feedback_gene_delta": (
                completed["summary"]["feedback_genes"] - observed["summary"]["feedback_genes"]
            ),
        }
    return {"sources": reports, "species_feedback_gain": species_reports,
            "promotion_policy": "No source is auto-promoted into interactions. Completed feedback uses only conflict-free regulatory_edge_candidates."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=OUT)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        result = qualify(conn)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.report.write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
