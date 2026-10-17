#!/usr/bin/env python3
"""Release gates for cross-species edge and sign transfer."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "grn.sqlite3"
REPORT = ROOT / "docs" / "benchmarks" / "cross-species-transfer-release-gates.json"


def verify(conn: sqlite3.Connection) -> dict:
    checks = {}
    checks["calibration_has_independent_cases"] = conn.execute(
        "SELECT COALESCE(SUM(cases),0) FROM cross_species_transfer_calibration"
    ).fetchone()[0] > 0
    checks["calibration_has_supported_classes"] = conn.execute(
        "SELECT COUNT(*) FROM cross_species_transfer_calibration WHERE gate_pass=1"
    ).fetchone()[0] > 0
    checks["conflicts_excluded_from_evidence"] = conn.execute("""
        SELECT COUNT(*) FROM orthology_transfer_candidates c
        JOIN regulatory_evidence r ON r.species=c.species AND r.source_id=c.source_id
          AND r.target_id=c.target_id AND r.relation_type=c.relation_type
        WHERE c.status='sign_conflict' AND r.source_name='Conserved signed orthology'
    """).fetchone()[0] == 0
    checks["recursive_inferred_donors_excluded"] = conn.execute(
        "SELECT COUNT(*) FROM orthology_transfer_candidates WHERE donor_sources LIKE '%Inferred:%'"
    ).fetchone()[0] == 0
    checks["supported_classes_pass_calibration"] = conn.execute("""
        SELECT COUNT(*) FROM regulatory_edge_candidates c
        LEFT JOIN orthology_transfer_candidates t ON t.species=c.species
          AND t.source_id=c.source_id AND t.target_id=c.target_id AND t.relation_type=c.relation_type
        LEFT JOIN cross_species_transfer_calibration m ON m.species=t.species
          AND m.relation_type=t.relation_type AND m.mapping_class=t.mapping_class
        WHERE c.support_class='supported_cross_species_transfer'
          AND (COALESCE(m.gate_pass,0)<>1 OR t.status<>'qualified'
               OR t.source_independent<>1
               OR (t.recipient_cis_support=0 AND t.recipient_binding_sources='[]'))
    """).fetchone()[0] == 0
    checks["unvalidated_transfers_are_exploratory"] = conn.execute("""
        SELECT COUNT(*) FROM regulatory_edge_candidates c
        JOIN orthology_transfer_candidates t ON t.species=c.species
          AND t.source_id=c.source_id AND t.target_id=c.target_id AND t.relation_type=c.relation_type
        WHERE t.status='unvalidated' AND c.evidence_tier<>'exploratory'
    """).fetchone()[0] == 0
    checks["scores_are_bounded"] = conn.execute(
        "SELECT COUNT(*) FROM orthology_transfer_candidates "
        "WHERE edge_score<0 OR edge_score>1 OR sign_score<0 OR sign_score>1"
    ).fetchone()[0] == 0
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
            "passed": all(checks.values())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        report = verify(conn)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
