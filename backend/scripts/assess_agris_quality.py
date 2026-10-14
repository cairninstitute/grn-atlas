#!/usr/bin/env python3
"""Ablate expanded AGRIS evidence and measure its candidate/core contribution."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
import feedback_control  # noqa: E402
from scripts.build_regulatory_candidates import build  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
OUT = BACKEND / "data" / "agris_quality_assessment.json"
EXPANDED = "AGRIS AtRegNet expanded"


def measure(conn: sqlite3.Connection) -> dict:
    candidate_stats = build(conn)
    observed = feedback_control.analyze_feedback(
        conn, "arabidopsis", feedback_control.FeedbackParameters(
            max_cores=200, max_circuits=1, circuits_per_core=1,
            discover_systems=False,
        ),
    )
    completed = feedback_control.analyze_feedback(
        conn, "arabidopsis", feedback_control.FeedbackParameters(
            max_cores=200, max_circuits=1, circuits_per_core=1,
            discover_systems=False, include_candidates=True,
        ),
    )
    source_rows = conn.execute(
        "SELECT COUNT(*) FROM regulatory_evidence WHERE source_name=?", (EXPANDED,)
    ).fetchone()[0]
    citing_expanded = conn.execute(
        "SELECT COUNT(*) FROM regulatory_edge_candidates "
        "WHERE status='candidate' AND evidence_sources LIKE ?", (f'%"{EXPANDED}"%',)
    ).fetchone()[0]
    candidate_keys = {
        tuple(row) for row in conn.execute(
            "SELECT species,source_id,target_id,relation_type "
            "FROM regulatory_edge_candidates WHERE status='candidate'"
        )
    }
    return {
        "expanded_source_records": source_rows,
        "candidate_build": candidate_stats,
        "candidates_citing_expanded_agris": citing_expanded,
        "observed_feedback_cores": observed["summary"]["feedback_cores"],
        "observed_feedback_genes": observed["summary"]["feedback_genes"],
        "completed_feedback_cores": completed["summary"]["feedback_cores"],
        "completed_feedback_genes": completed["summary"]["feedback_genes"],
        "_candidate_keys": candidate_keys,
    }


def assess(db_path: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="grn-agris-") as tmp:
        copy = Path(tmp) / "grn.sqlite3"
        shutil.copy2(db_path, copy)
        with sqlite3.connect(copy) as conn:
            with_expanded = measure(conn)
            conn.execute("DELETE FROM regulatory_evidence WHERE source_name=?", (EXPANDED,))
            conn.commit()
            without_expanded = measure(conn)
    with_keys = with_expanded.pop("_candidate_keys")
    without_keys = without_expanded.pop("_candidate_keys")
    delta = {
        key: with_expanded[key] - without_expanded[key]
        for key in (
            "observed_feedback_cores", "observed_feedback_genes", "completed_feedback_cores",
            "completed_feedback_genes",
        )
    }
    delta["candidate_edges_added"] = len(with_keys - without_keys)
    delta["candidate_edges_removed_by_conflict"] = len(without_keys - with_keys)
    return {
        "with_expanded_agris": with_expanded,
        "without_expanded_agris": without_expanded,
        "delta": delta,
        "interpretation_boundary": (
            "Expanded AGRIS is retained only as evidence. It is not promoted to the observed "
            "interaction graph; conflict-free candidates require the normal evidence policy."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=OUT)
    args = parser.parse_args()
    result = assess(args.db)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.report.write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
