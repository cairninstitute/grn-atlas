#!/usr/bin/env python3
"""Verify that a clean bootstrap produced every required release data layer."""

import json
import sqlite3
import sys
from pathlib import Path


DATA = Path(__file__).resolve().parent.parent / "data"
DB = DATA / "grn.sqlite3"


def scalar(conn, query, params=()):
    return conn.execute(query, params).fetchone()[0]


def main():
    failures = []
    required_files = {
        "regulation_arabidopsis.tsv": 90_000,
        "atrm_regulations.tsv": 1_400,
    }
    file_counts = {}
    for filename, minimum in required_files.items():
        path = DATA / filename
        count = sum(1 for _ in path.open()) if path.exists() else 0
        file_counts[filename] = count
        if count < minimum:
            failures.append(f"{filename}: {count:,} rows; expected at least {minimum:,}")

    if not DB.exists():
        failures.append(f"database missing: {DB}")
        report = {"status": "fail", "files": file_counts, "failures": failures}
        print(json.dumps(report, indent=2))
        return 1

    conn = sqlite3.connect(DB)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required_tables = {
        "genes", "interactions", "perturbation_observations",
        "regulatory_evidence", "source_import_runs", "regulatory_edge_candidates",
        "regulatory_candidate_impacts", "perturbation_sign_consensus",
        "perturbation_sign_calibration",
    }
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        failures.append("missing tables: " + ", ".join(missing_tables))

    counts = {}
    if not missing_tables:
        checks = {
            "genes": ("SELECT COUNT(*) FROM genes", (), 140_000),
            "interactions": ("SELECT COUNT(*) FROM interactions", (), 1_300_000),
            "connectf_observations": (
                "SELECT COUNT(*) FROM perturbation_observations WHERE dataset_label='connectf_target'",
                (), 100_000,
            ),
            "knocktf_arabidopsis": (
                "SELECT COUNT(*) FROM perturbation_observations WHERE dataset_label='knocktf' AND species='arabidopsis'",
                (), 100_000,
            ),
            "knocktf_human": (
                "SELECT COUNT(*) FROM perturbation_observations WHERE dataset_label='knocktf' AND species='human'",
                (), 1_500_000,
            ),
            "knocktf_mouse": (
                "SELECT COUNT(*) FROM perturbation_observations WHERE dataset_label='knocktf' AND species='mouse'",
                (), 300_000,
            ),
            "external_evidence": ("SELECT COUNT(*) FROM regulatory_evidence", (), 1_000_000),
            "regulatory_candidates": (
                "SELECT COUNT(*) FROM regulatory_edge_candidates", (), 150_000,
            ),
            "perturbation_consensus": (
                "SELECT COUNT(*) FROM perturbation_sign_consensus WHERE status='accepted'",
                (), 80_000,
            ),
            "ranked_candidate_impacts": (
                "SELECT COUNT(*) FROM regulatory_candidate_impacts", (), 35_000,
            ),
        }
        for label, (query, params, minimum) in checks.items():
            count = scalar(conn, query, params)
            counts[label] = count
            if count < minimum:
                failures.append(f"{label}: {count:,}; expected at least {minimum:,}")

        imports = {}
        for name, status, raw_counts in conn.execute(
            "SELECT source_name, status, counts FROM source_import_runs ORDER BY import_run_id"
        ):
            imports[name] = {"status": status, "counts": json.loads(raw_counts)}

        required_sources = {
            "CollecTRI": 40_000,
            "SIGNOR": 2_000,
            "AGRIS AtRegNet": 3_500,
            "AGRIS AtRegNet expanded": 6_000,
            "TFLink small-scale": 15_000,
            "ChIP-Atlas": 800_000,
            "Expression Atlas reviewed perturbations": 25,
            "ConnecTF experiment evidence": 140_000,
            "Perturbation sign consensus": 80_000,
            "Conserved signed orthology": 0,
        }
        for source, minimum in required_sources.items():
            if imports.get(source, {}).get("status") != "complete":
                failures.append(f"{source}: no complete source import run")
                continue
            stored = scalar(
                conn, "SELECT COUNT(*) FROM regulatory_evidence WHERE source_name=?", (source,)
            )
            counts[f"source:{source}"] = stored
            if stored < minimum:
                failures.append(f"{source}: {stored:,} evidence rows; expected at least {minimum:,}")
    else:
        imports = {}
    conn.close()

    report = {
        "status": "pass" if not failures else "fail",
        "profile": "release-source-data",
        "files": file_counts,
        "counts": counts,
        "external_imports": imports,
        "failures": failures,
        "note": (
            "Expression quantification, inferred_edges, and genome-scale motif scans are "
            "compute-derived optional layers and are not part of this source-data profile."
        ),
    }
    print(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
