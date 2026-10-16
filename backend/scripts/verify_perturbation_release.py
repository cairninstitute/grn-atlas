#!/usr/bin/env python3
"""Enforce release gates for perturbation-derived regulatory signs."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "grn.sqlite3"
REPORT = ROOT / "docs" / "benchmarks" / "perturbation-release-gates.json"


def verify(conn: sqlite3.Connection) -> dict:
    checks = {}
    checks["consensus_has_provenance"] = conn.execute(
        "SELECT COUNT(*) FROM perturbation_sign_consensus WHERE model_version='' "
        "OR datasets='' OR experiment_ids=''"
    ).fetchone()[0] == 0
    checks["conflicts_not_emitted_as_evidence"] = conn.execute("""
        SELECT COUNT(*) FROM perturbation_sign_consensus c
        JOIN regulatory_evidence r
          ON r.species=c.species AND r.source_id=c.source_id AND r.target_id=c.target_id
        WHERE c.status='sign_conflict' AND r.source_name='Perturbation sign consensus'
    """).fetchone()[0] == 0
    checks["supported_candidates_pass_calibration"] = conn.execute("""
        SELECT COUNT(*) FROM regulatory_edge_candidates c
        LEFT JOIN perturbation_sign_calibration m
          ON m.species=c.species AND m.relation_type=c.relation_type
        WHERE c.support_class='binding_plus_perturbation'
          AND COALESCE(m.gate_pass,0)<>1
    """).fetchone()[0] == 0
    checks["uncalibrated_calls_are_exploratory"] = conn.execute("""
        SELECT COUNT(*) FROM regulatory_edge_candidates
        WHERE support_class='binding_plus_uncalibrated_perturbation'
          AND evidence_tier<>'exploratory'
    """).fetchone()[0] == 0
    checks["observed_interactions_not_promoted"] = conn.execute("""
        SELECT COUNT(*) FROM interactions
        WHERE sign_evidence NOT IN ('measured','perturbation','unknown')
           OR sign_evidence IS NULL
    """).fetchone()[0] == 0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        report = verify(conn)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
