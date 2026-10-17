#!/usr/bin/env python3
"""Calibrate transferred signs against source-disjoint recipient observations."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
REPORT = BACKEND.parent / "docs" / "benchmarks" / "cross-species-transfer-calibration.json"
MODEL = "cross-species-transfer-v1"


def _items(value: str | None) -> set[str]:
    try:
        parsed = json.loads(value or "[]")
        return {str(item) for item in parsed} if isinstance(parsed, list) else set()
    except (TypeError, json.JSONDecodeError):
        return set()


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if not total:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


def _distance_stratum(donor: str, recipient: str) -> str:
    solanaceae = {"tomato", "petunia", "potato", "pepper"}
    if {donor, recipient} <= {"human", "mouse"}:
        return "close_mammal"
    if donor in solanaceae and recipient in solanaceae:
        return "close_solanaceae"
    if "rice" in {donor, recipient}:
        return "monocot_dicot"
    return "distant_eudicot"


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def calibrate(conn: sqlite3.Connection) -> dict:
    conn.executescript("""
        DROP TABLE IF EXISTS cross_species_transfer_calibration;
        CREATE TABLE cross_species_transfer_calibration (
            species TEXT NOT NULL, relation_type TEXT NOT NULL, mapping_class TEXT NOT NULL,
            cases INTEGER NOT NULL, agreements INTEGER NOT NULL, precision REAL NOT NULL,
            baseline_rate REAL NOT NULL, lift REAL NOT NULL, wilson_lower_95 REAL NOT NULL,
            edge_validation_rate REAL NOT NULL, gate_pass INTEGER NOT NULL,
            model_version TEXT NOT NULL,
            PRIMARY KEY(species,relation_type,mapping_class)
        );
    """)
    truths = {}
    species_signs: dict[str, Counter] = defaultdict(Counter)
    for species, source, target, sign, sources, pmids in conn.execute(
        "SELECT g.species,i.source_id,i.target_id,COALESCE(i.sign,i.regulation_type),i.sources,i.pmids "
        "FROM interactions i JOIN genes g ON g.id=i.source_id "
        "WHERE i.sign_evidence='measured' AND COALESCE(i.sign,i.regulation_type) "
        "IN ('activation','repression')"
    ):
        truth_sources = {item for item in _items(sources) if not item.startswith("Inferred:")}
        if not truth_sources:
            continue
        truths[(species, source, target)] = (sign, truth_sources, _items(pmids))
        species_signs[species][sign] += 1

    grouped: dict[tuple[str, str, str], list[bool]] = defaultdict(list)
    edge_validation: dict[tuple[str, str, str], list[bool]] = defaultdict(list)
    distance_outcomes: dict[str, list[bool]] = defaultdict(list)
    excluded = Counter()
    candidate_columns = _columns(conn, "orthology_transfer_candidates")
    metadata_sql = "metadata" if "metadata" in candidate_columns else "'{}'"
    for row in conn.execute(
            "SELECT species,source_id,target_id,relation_type,mapping_class,donor_sources,donor_pmids,"
            "recipient_binding_sources,recipient_cis_support,status,donor_species," + metadata_sql + " "
            "FROM orthology_transfer_candidates"
        ):
        (species, source, target, relation, mapping_class, donor_sources, donor_pmids,
         binding_sources, cis_support, status, donor_species_json, metadata_json) = row
        key = (species, relation, mapping_class)
        edge_validation[key].append(bool(_items(binding_sources) or cis_support))
        try:
            metadata = json.loads(metadata_json or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        if mapping_class == "paralog_aware_synteny":
            excluded["paralog_aware_mapping"] += 1
            continue
        if metadata and int(metadata.get("supported_donor_count", 0)) < 1:
            excluded["exploratory_donor_only"] += 1
            continue
        truth = truths.get((species, source, target))
        if not truth:
            continue
        truth_sign, truth_sources, truth_pmids = truth
        if _items(donor_sources) & truth_sources:
            excluded["shared_source"] += 1
            continue
        if _items(donor_pmids) & truth_pmids:
            excluded["shared_publication"] += 1
            continue
        if status == "sign_conflict":
            excluded["donor_sign_conflict"] += 1
            continue
        grouped[key].append(relation == truth_sign)
        for donor_species in _items(donor_species_json):
            distance_outcomes[_distance_stratum(donor_species, species)].append(relation == truth_sign)

    rows = []
    classes = []
    for key in sorted(set(grouped) | set(edge_validation)):
        species, relation, mapping_class = key
        outcomes = grouped.get(key, [])
        cases, agreements = len(outcomes), sum(outcomes)
        precision = agreements / cases if cases else 0.0
        total = sum(species_signs[species].values())
        baseline = species_signs[species][relation] / total if total else 0.0
        lift = precision - baseline
        lower = _wilson_lower(agreements, cases)
        edge_rate = sum(edge_validation[key]) / len(edge_validation[key]) if edge_validation[key] else 0.0
        gate = (mapping_class != "paralog_aware_synteny" and cases >= 50
                and precision >= 0.80 and lift >= 0.02 and lower > baseline)
        row = (species, relation, mapping_class, cases, agreements, precision, baseline,
               lift, lower, edge_rate, int(gate), MODEL)
        rows.append(row)
        classes.append({
            "species": species, "relation_type": relation, "mapping_class": mapping_class,
            "cases": cases, "agreements": agreements, "precision": round(precision, 4),
            "baseline_rate": round(baseline, 4), "lift": round(lift, 4),
            "wilson_lower_95": round(lower, 4), "recipient_edge_validation_rate": round(edge_rate, 4),
            "gate_pass": gate,
        })
    conn.executemany("INSERT INTO cross_species_transfer_calibration VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "model_version": MODEL,
        "leakage_controls": [
            "donor and recipient evidence sources must be disjoint",
            "donor and recipient PubMed identifiers must be disjoint",
            "recipient truth is restricted to measured signed interactions",
            "donor-sign conflicts are excluded",
            "exploratory-only donor evidence is excluded",
            "bounded-paralog projections are excluded",
        ],
        "thresholds": {"minimum_cases": 50, "minimum_precision": 0.8,
                       "minimum_lift_over_class_base_rate": 0.02,
                       "wilson_lower_must_exceed_base_rate": True},
        "excluded_overlaps": dict(excluded), "classes": classes,
        "species_held_out": {
            species: {"independent_cases": sum(row["cases"] for row in classes if row["species"] == species),
                      "status": ("evaluated" if sum(row["cases"] for row in classes if row["species"] == species)
                                 else "insufficient_independent_cases")}
            for species in sorted({row["species"] for row in classes})
        },
        "evolutionary_distance_strata": {
            name: {"cases": len(values), "precision": round(sum(values) / len(values), 4)}
            for name, values in sorted(distance_outcomes.items()) if values
        },
        "supported_classes": [row for row in classes if row["gate_pass"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        result = calibrate(conn)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
