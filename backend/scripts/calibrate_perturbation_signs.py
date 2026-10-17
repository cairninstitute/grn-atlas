#!/usr/bin/env python3
"""Calibrate perturbation consensus signs against independently curated edges."""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "grn.sqlite3"
DEFAULT_REPORT = ROOT / "docs" / "benchmarks" / "perturbation-sign-calibration.json"
MODEL_VERSION = "perturbation-calibration-v1"
MIN_CASES = 50
MIN_PRECISION = 0.80
MIN_LIFT = 0.02


def _items(value: str | None) -> set[str]:
    try:
        parsed = json.loads(value or "[]")
        return {str(item) for item in parsed} if isinstance(parsed, list) else set()
    except (TypeError, json.JSONDecodeError):
        return set()


def _source_key(value: str) -> str:
    value = value.removeprefix("Perturbation:").casefold()
    return re.sub(r"[^a-z0-9]+", "", value)


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


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
    interaction_columns = _columns(conn, "interactions")
    source_expr = "sources" if "sources" in interaction_columns else "'[]'"
    pmid_expr = "pmids" if "pmids" in interaction_columns else "'[]'"
    gene_species = {}
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='genes'"
    ).fetchone():
        gene_species = dict(conn.execute("SELECT id,species FROM genes"))

    truths: dict[tuple[str | None, str, str], list[tuple[str, set[str], set[str]]]] = defaultdict(list)
    for source, target, sign, sources, pmids in conn.execute(
        f"SELECT source_id,target_id,COALESCE(sign,regulation_type),{source_expr},{pmid_expr} "
        "FROM interactions WHERE sign_evidence='measured' "
        "AND COALESCE(sign,regulation_type) IN ('activation','repression')"
    ):
        truths[(gene_species.get(source), source, target)].append(
            (sign, _items(sources), _items(pmids))
        )
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='regulatory_evidence'"
    ).fetchone():
        for species, source, target, sign, source_name, pmids in conn.execute(
            "SELECT species,source_id,target_id,relation_type,source_name,pmids "
            "FROM regulatory_evidence WHERE evidence_layer='direct_signed' "
            "AND directness='direct' AND relation_type IN ('activation','repression')"
        ):
            truths[(species, source, target)].append(
                (sign, {source_name}, _items(pmids))
            )

    consensus_columns = _columns(conn, "perturbation_sign_consensus")
    datasets_expr = "datasets" if "datasets" in consensus_columns else "'[]'"
    predictions = conn.execute(
        f"SELECT species,source_id,target_id,relation_type,confidence,{datasets_expr} "
        "FROM perturbation_sign_consensus WHERE status='accepted'"
    ).fetchall()
    rows = []
    excluded = Counter()
    for species, source, target, predicted, confidence, datasets in predictions:
        truth_records = truths.get((species, source, target), truths.get((None, source, target), []))
        if not truth_records:
            continue
        truth_signs = {record[0] for record in truth_records}
        if len(truth_signs) != 1:
            excluded["conflicting_truth"] += 1
            continue
        prediction_sources = {_source_key(item) for item in _items(datasets)}
        truth_sources = {_source_key(item) for record in truth_records for item in record[1]}
        if prediction_sources & truth_sources:
            excluded["shared_source"] += 1
            continue
        rows.append((species, predicted, next(iter(truth_signs)), float(confidence)))
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
            "truth is restricted to measured interactions and independently direct-signed evidence",
            "conflicting recipient truth is excluded",
            "perturbation datasets and truth sources must be disjoint",
            "release gates are evaluated separately by species and predicted sign",
        ],
        "excluded_overlaps": dict(excluded),
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
