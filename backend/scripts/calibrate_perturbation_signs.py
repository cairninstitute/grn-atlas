#!/usr/bin/env python3
"""Calibrate perturbation consensus signs against independently curated edges."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "grn.sqlite3"
DEFAULT_REPORT = ROOT / "docs" / "benchmarks" / "perturbation-sign-calibration.json"
MODEL_VERSION = "perturbation-calibration-v1"
MIN_CASES = 50
MIN_PRECISION = 0.80
MIN_LIFT = 0.02


def wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if not total:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    center = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (center - margin) / denominator


def calibrate(conn: sqlite3.Connection) -> dict:
    conn.executescript("""
        DROP TABLE IF EXISTS perturbation_sign_calibration;
        CREATE TABLE perturbation_sign_calibration (
            species TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            cases INTEGER NOT NULL,
            agreements INTEGER NOT NULL,
            precision REAL NOT NULL,
            baseline_rate REAL NOT NULL,
            lift REAL NOT NULL,
            wilson_lower REAL NOT NULL,
            gate_pass INTEGER NOT NULL,
            model_version TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            PRIMARY KEY (species, relation_type)
        );
    """)
    rows = conn.execute("""
        SELECT c.species,c.relation_type,
               COALESCE(i.sign,i.regulation_type) AS observed_sign,
               c.confidence
        FROM perturbation_sign_consensus c
        JOIN interactions i
          ON i.source_id=c.source_id AND i.target_id=c.target_id
        WHERE c.status='accepted' AND i.sign_evidence='measured'
          AND COALESCE(i.sign,i.regulation_type) IN ('activation','repression')
        ORDER BY c.species,c.relation_type
    """).fetchall()
    by_species = defaultdict(list)
    by_class = defaultdict(list)
    for species, predicted, observed, confidence in rows:
        by_species[species].append((predicted, observed, float(confidence)))
        by_class[(species, predicted)].append((observed, float(confidence)))
    generated_at = datetime.now(timezone.utc).isoformat()
    classes = []
    values = []
    for (species, relation), records in sorted(by_class.items()):
        total = len(records)
        agreements = sum(observed == relation for observed, _ in records)
        precision = agreements / total
        species_records = by_species[species]
        baseline = sum(observed == relation for _, observed, _ in species_records) / len(species_records)
        lower = wilson_lower(agreements, total)
        lift = precision - baseline
        gate_pass = (
            total >= MIN_CASES and precision >= MIN_PRECISION
            and lift >= MIN_LIFT and lower > baseline
        )
        values.append((species, relation, total, agreements, precision, baseline, lift,
                       lower, int(gate_pass), MODEL_VERSION, generated_at))
        classes.append({
            "species": species,
            "relation_type": relation,
            "cases": total,
            "agreements": agreements,
            "precision": round(precision, 4),
            "baseline_rate": round(baseline, 4),
            "lift": round(lift, 4),
            "wilson_lower_95": round(lower, 4),
            "gate_pass": gate_pass,
        })
    conn.executemany(
        "INSERT INTO perturbation_sign_calibration VALUES (?,?,?,?,?,?,?,?,?,?,?)", values,
    )
    conn.commit()
    total = len(rows)
    agreements = sum(predicted == observed for records in by_species.values()
                     for predicted, observed, _ in records)
    majority_correct = sum(
        max(sum(observed == sign for _, observed, _ in records) for sign in ("activation", "repression"))
        for records in by_species.values()
    )
    return {
        "generated_at": generated_at,
        "model_version": MODEL_VERSION,
        "leakage_controls": [
            "literature_curated observations are excluded from consensus generation",
            "only interactions with sign_evidence=measured are calibration truth",
            "release gates are evaluated separately by species and predicted sign",
        ],
        "thresholds": {
            "minimum_cases": MIN_CASES,
            "minimum_precision": MIN_PRECISION,
            "minimum_lift_over_class_base_rate": MIN_LIFT,
            "wilson_lower_must_exceed_base_rate": True,
        },
        "overall": {
            "cases": total,
            "accuracy": round(agreements / total, 4) if total else None,
            "species_majority_baseline": round(majority_correct / total, 4) if total else None,
            "passes_global_baseline": agreements > majority_correct,
        },
        "classes": classes,
        "supported_classes": [
            {"species": row["species"], "relation_type": row["relation_type"]}
            for row in classes if row["gate_pass"]
        ],
        "interpretation": (
            "A failed class remains exploratory. Perturbation response may be indirect or "
            "context-specific and is not promoted as a global regulatory sign."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        report = calibrate(conn)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
