#!/usr/bin/env python3
"""Summarize plant transfer hypotheses and compare them with a saved baseline."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "data" / "grn.sqlite3"
REPORT = ROOT / "docs" / "benchmarks" / "plant-transfer-expansion.json"
PLANTS = {"arabidopsis", "pepper", "petunia", "potato", "rice", "tomato"}


def _metadata(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def snapshot(conn: sqlite3.Connection) -> dict:
    species = defaultdict(lambda: {
        "total": 0, "status": Counter(), "mapping_class": Counter(),
        "donor_tier": Counter(), "donor_class": Counter(),
    })
    for recipient, status, mapping_class, metadata_json in conn.execute(
        "SELECT species,status,mapping_class,metadata FROM orthology_transfer_candidates"
    ):
        if recipient not in PLANTS:
            continue
        entry = species[recipient]
        entry["total"] += 1
        entry["status"][status] += 1
        entry["mapping_class"][mapping_class] += 1
        metadata = _metadata(metadata_json)
        entry["donor_tier"][metadata.get("donor_evidence_tier", "legacy_unknown")] += 1

    # donor_edges lives outside metadata in the current schema.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(orthology_transfer_candidates)")}
    if "donor_edges" in columns:
        for recipient, donor_edges in conn.execute(
            "SELECT species,donor_edges FROM orthology_transfer_candidates"
        ):
            if recipient not in PLANTS:
                continue
            try:
                edges = json.loads(donor_edges or "[]")
            except (TypeError, json.JSONDecodeError):
                edges = []
            classes = {edge.get("donor_class", "legacy_observed_interaction")
                       for edge in edges if isinstance(edge, dict)}
            if not classes:
                classes = {"legacy_or_unspecified"}
            for donor_class in classes:
                species[recipient]["donor_class"][donor_class] += 1

    supported = Counter()
    exploratory = Counter()
    for recipient, tier, count in conn.execute(
        "SELECT species,evidence_tier,COUNT(*) FROM regulatory_edge_candidates "
        "WHERE evidence_sources LIKE '%Conserved signed orthology%' GROUP BY species,evidence_tier"
    ):
        if recipient in PLANTS:
            (supported if tier == "supported" else exploratory)[recipient] += count

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "species": {
            name: {
                "total": values["total"],
                "status": dict(sorted(values["status"].items())),
                "mapping_class": dict(sorted(values["mapping_class"].items())),
                "donor_tier": dict(sorted(values["donor_tier"].items())),
                "donor_class": dict(sorted(values["donor_class"].items())),
                "supported_candidates": supported[name],
                "exploratory_candidates": exploratory[name],
            }
            for name, values in sorted(species.items())
        },
    }


def _delta(current: dict, baseline: dict) -> dict:
    result = {}
    names = sorted(set(current.get("species", {})) | set(baseline.get("species", {})))
    for name in names:
        now = current.get("species", {}).get(name, {})
        before = baseline.get("species", {}).get(name, {})
        result[name] = {
            key: int(now.get(key, 0)) - int(before.get(key, 0))
            for key in ("total", "supported_candidates", "exploratory_candidates")
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        report = snapshot(conn)
    if args.baseline and args.baseline.exists():
        baseline = json.loads(args.baseline.read_text())
        baseline_path = args.baseline.resolve()
        try:
            report["baseline"] = str(baseline_path.relative_to(ROOT))
        except ValueError:
            report["baseline"] = str(baseline_path)
        report["delta"] = _delta(report, baseline)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
