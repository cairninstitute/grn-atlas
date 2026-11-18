#!/usr/bin/env python3
"""Verify that a clean bootstrap produced every required release data layer."""

import json
import sqlite3
import sys
from pathlib import Path


DATA = Path(__file__).resolve().parent.parent / "data"
DB = DATA / "grn.sqlite3"
SUMMARY = DATA / "atlas_summary.json"
EXPECTED_DIGEST = DATA / "expected_digest.sha256"
CONTENT_DIGEST = DATA / "content_digest.json"
SOURCE_LOCK = DATA / "source_lock.json"


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
        "orthology_transfer_mappings", "orthology_transfer_candidates",
        "cross_species_transfer_calibration",
        "directed_inferred_edges", "scrna_datasets", "scrna_clusters",
        "scrna_cluster_expression", "celltype_regulatory_edges",
        "cis_support_scores",
    }
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        failures.append("missing tables: " + ", ".join(missing_tables))

    counts = {}
    if not missing_tables:
        checks = {
            "genes": ("SELECT COUNT(*) FROM genes", (), 142_000),
            "interactions": ("SELECT COUNT(*) FROM interactions", (), 4_200_000),
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
            "external_evidence": ("SELECT COUNT(*) FROM regulatory_evidence", (), 7_000_000),
            "regulatory_candidates": (
                "SELECT COUNT(*) FROM regulatory_edge_candidates", (), 270_000,
            ),
            "perturbation_consensus": (
                "SELECT COUNT(*) FROM perturbation_sign_consensus WHERE status='accepted'",
                (), 100_000,
            ),
            "cross_species_transfer_candidates": (
                "SELECT COUNT(*) FROM orthology_transfer_candidates", (), 40_000,
            ),
            "ranked_candidate_impacts": (
                "SELECT COUNT(*) FROM regulatory_candidate_impacts", (), 140_000,
            ),
            "directed_inferred_edges": (
                "SELECT COUNT(*) FROM directed_inferred_edges", (), 500_000,
            ),
            "scrna_datasets": (
                "SELECT COUNT(*) FROM scrna_datasets", (), 2,
            ),
            "celltype_regulatory_edges": (
                "SELECT COUNT(*) FROM celltype_regulatory_edges", (), 1_200_000,
            ),
            "cis_support_scores": (
                "SELECT COUNT(*) FROM cis_support_scores", (), 400_000,
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

        bad_json = scalar(
            conn,
            "SELECT COUNT(*) FROM interactions "
            "WHERE sources IS NOT NULL AND sources != '' AND json_valid(sources) = 0",
        )
        counts["malformed_sources"] = bad_json
        if bad_json > 0:
            failures.append(f"interactions.sources: {bad_json:,} rows with invalid JSON")

        required_sources = {
            "CollecTRI": 40_000,
            "SIGNOR": 1_000,
            "AGRIS AtRegNet": 3_500,
            "AGRIS AtRegNet expanded": 6_000,
            "TFLink small-scale": 15_000,
            "ChIP-Atlas": 800_000,
            "PlantTFDB": 800_000,
            "ReMap": 600_000,
            "UniBind": 100_000,
            "DirectBinding": 150_000,
            "Expression Atlas reviewed perturbations": 10,
            "ConnecTF experiment evidence": 140_000,
            "Perturbation sign consensus": 80_000,
            "Conserved signed orthology": 13_000,
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
        ea_import = imports.get("Expression Atlas reviewed perturbations", {})
        ea_counts = ea_import.get("counts", {})
        known_gaps = {
            "Expression Atlas reviewed perturbations": {
                "unmapped_targets": ea_counts.get("unmapped_or_self", 0),
                "unmapped_regulators": ea_counts.get("unmapped_regulator", 0),
                "reason": (
                    "Rice Expression Atlas results use RAP-DB gene IDs; "
                    "crosswalk covers TFs in the atlas gene table but most "
                    "target genes (non-TFs) are absent from the gene table"
                ),
            },
        }
        for source, gap_info in known_gaps.items():
            stored = scalar(
                conn, "SELECT COUNT(*) FROM regulatory_evidence WHERE source_name=?", (source,)
            )
            counts[f"source:{source}"] = stored
            gap_info["evidence_rows"] = stored
    else:
        imports = {}
        known_gaps = {}

    if EXPECTED_DIGEST.exists() and CONTENT_DIGEST.exists():
        expected = EXPECTED_DIGEST.read_text().strip()
        actual = json.loads(CONTENT_DIGEST.read_text()).get("atlas_digest", "")
        counts["content_digest_match"] = expected == actual
        if expected != actual:
            failures.append(
                f"content digest mismatch: expected {expected[:16]}… got {actual[:16]}…"
            )

    if SOURCE_LOCK.exists() and not missing_tables:
        lock = json.loads(SOURCE_LOCK.read_text())
        db_hashes = {}
        for name, sha in conn.execute(
            "SELECT source_name, sha256 FROM source_import_runs "
            "WHERE status='complete' ORDER BY import_run_id DESC"
        ):
            if name not in db_hashes:
                db_hashes[name] = sha
        lock_mismatches = []
        for name, info in lock.items():
            expected_sha = info.get("sha256")
            actual_sha = db_hashes.get(name)
            if expected_sha and actual_sha and expected_sha != actual_sha:
                lock_mismatches.append(name)
        counts["source_lock_mismatches"] = len(lock_mismatches)
        if lock_mismatches:
            failures.append(
                f"source hash mismatch vs lock: {', '.join(lock_mismatches)}"
            )

    analysis_tables = {
        "directed_inferred_edges": ("directed_inferred_edges", "inferred_edges"),
        "celltype_regulatory_edges": ("celltype_regulatory_edges",),
        "perturbation_observations": ("perturbation_observations",),
        "orthology_transfer_candidates": ("orthology_transfer_candidates",),
        "chromatin_peaks": ("chromatin_peaks",),
        "structural_binding_predictions": ("structural_binding_predictions",),
    }
    summary = {
        "verified": not failures,
        "genes": scalar(conn, "SELECT COUNT(*) FROM genes") if "genes" in tables else 0,
        "interactions": scalar(conn, "SELECT COUNT(*) FROM interactions") if "interactions" in tables else 0,
        "species_list": [
            row[0] for row in conn.execute(
                "SELECT DISTINCT species FROM genes ORDER BY species"
            )
        ] if "genes" in tables else [],
        "analysis_layers": {},
    }
    for label, candidates in analysis_tables.items():
        table = next((candidate for candidate in candidates if candidate in tables), None)
        summary["analysis_layers"][label] = (
            scalar(conn, f'SELECT COUNT(*) FROM "{table}"') if table else 0
        )
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")
    conn.close()

    report = {
        "status": "pass" if not failures else "fail",
        "profile": "release-source-data",
        "files": file_counts,
        "counts": counts,
        "external_imports": imports,
        "known_gaps": known_gaps,
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
