#!/usr/bin/env python3
"""Benchmark biological control-system discovery across every atlas species."""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

import feedback_control  # noqa: E402
import main  # noqa: E402


def main_cli() -> None:
    out_dir = ROOT / "docs" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    species_list = [
        row[0] for row in main.db.conn.execute(
            "SELECT DISTINCT species FROM genes ORDER BY species"
        ).fetchall()
    ]
    rows = []
    details = {}
    circadian = None
    for species in species_list:
        started = time.perf_counter()
        result = feedback_control.analyze_feedback(main.db.conn, species)
        elapsed = time.perf_counter() - started
        systems = result["systems"]
        architecture_counts = Counter(system["architecture"] for system in systems)
        row = {
            "species": species,
            "seconds": round(elapsed, 3),
            "signed_edges": result["graph"]["edges"],
            "feedback_cores": result["summary"]["feedback_cores"],
            "feedback_edges": result["summary"]["feedback_edges"],
            "exact_cycle_catalogs": result["summary"]["exact_cycle_catalogs"],
            "cataloged_cycles": result["summary"]["cataloged_cycles"],
            "core_relationships": result["summary"]["core_relationships"],
            "core_groups": result["summary"]["core_groups"],
            "systems": len(systems),
            "annotation_supported": sum(
                system["discovery_mode"] == "annotation_supported" for system in systems
            ),
            "de_novo": sum(system["discovery_mode"] == "de_novo_topology" for system in systems),
            "partial_architectures": sum(
                system["completeness"] == "partial_architecture" for system in systems
            ),
        }
        rows.append(row)
        details[species] = {
            "summary": row,
            "architecture_counts": dict(sorted(architecture_counts.items())),
            "core_groups": result["core_groups"],
            "top_systems": [
                {
                    "rank": system["rank"],
                    "name": system["name"],
                    "architecture": system["architecture"],
                    "score": system["score"],
                    "discovery_mode": system["discovery_mode"],
                    "completeness": system["completeness"],
                }
                for system in systems[:10]
            ],
        }
        if species == "arabidopsis":
            circadian = next(
                (system for system in systems if "circadian" in system["name"].lower()),
                None,
            )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm_version": feedback_control.ALGORITHM_VERSION,
        "species_count": len(species_list),
        "checks": {
            "all_species_completed": len(rows) == len(species_list),
            "arabidopsis_circadian_recovered": circadian is not None,
            "arabidopsis_circadian_partial": bool(
                circadian and circadian["completeness"] == "partial_architecture"
            ),
        },
        "species": details,
    }
    (out_dir / "control-system-discovery.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    with (out_dir / "control-system-discovery.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]) if rows else ["species"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(report["checks"], indent=2))


if __name__ == "__main__":
    main_cli()
