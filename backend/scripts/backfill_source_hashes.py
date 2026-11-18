#!/usr/bin/env python3
"""Retroactively compute sha256 hashes for source imports with cached local files.

Scans source_import_runs for entries missing sha256, looks up the matching
cached data file, and fills in the hash. For derived/computed imports with
no single source file, computes a composite hash from the import's code
and input data.

Usage:
    venv/bin/python backend/scripts/backfill_source_hashes.py
    venv/bin/python backend/scripts/backfill_source_hashes.py --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DB = BACKEND / "data" / "grn.sqlite3"

SOURCE_FILE_MAP = {
    "Perturbation sign consensus": [],
    "Conserved signed orthology": [],
    "DirectBinding": [BACKEND / "data" / "dapseq_arabidopsis.tsv"],
    "ChIP-Atlas": [],
    "TFLink small-scale": [],
    "CollecTRI": [],
    "SIGNOR": [],
    "PlantTFDB": [],
    "ReMap": [],
    "UniBind": [],
    "ConnecTF experiment evidence": [],
    "Expression Atlas reviewed perturbations": [],
}

LOADER_SCRIPT_MAP = {
    "Perturbation sign consensus": BACKEND / "scripts" / "compute_perturbation_sign.py",
    "Conserved signed orthology": BACKEND / "scripts" / "build_signed_orthology.py",
    "DirectBinding": BACKEND / "scripts" / "load_direct_binding.py",
    "ChIP-Atlas": BACKEND / "scripts" / "load_chip_atlas.py",
    "TFLink small-scale": BACKEND / "scripts" / "load_tflink.py",
    "PlantTFDB": BACKEND / "scripts" / "fetch_planttfdb_edges.py",
    "ReMap": BACKEND / "scripts" / "load_remap.py",
    "UniBind": BACKEND / "scripts" / "load_unibind.py",
    "ConnecTF experiment evidence": BACKEND / "scripts" / "load_connectf_evidence.py",
    "Expression Atlas reviewed perturbations": BACKEND / "scripts" / "load_expression_atlas_perturbations.py",
}

CACHE_DIR_MAP = {
    "ChIP-Atlas": BACKEND / "data" / "chip_atlas_cache",
    "TFLink small-scale": BACKEND / "data" / "tflink_cache",
    "PlantTFDB": BACKEND / "data" / "planttfdb_cache",
    "ReMap": BACKEND / "data" / "remap_cache",
    "UniBind": BACKEND / "data" / "unibind_cache",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def composite_hash(parts: list[bytes | str]) -> str:
    digest = hashlib.sha256()
    for p in sorted(parts):
        digest.update(p.encode("utf-8") if isinstance(p, str) else p)
    return digest.hexdigest()


def compute_hash_for_source(source_name: str) -> str | None:
    data_files = SOURCE_FILE_MAP.get(source_name, [])
    if data_files:
        existing = [f for f in data_files if f.exists()]
        if existing:
            parts = [file_sha256(f) for f in existing]
            return composite_hash(parts) if len(parts) > 1 else parts[0]

    cache_dir = CACHE_DIR_MAP.get(source_name)
    if cache_dir and cache_dir.exists():
        cached_files = sorted(cache_dir.glob("*"))
        if cached_files:
            parts = [file_sha256(f) for f in cached_files if f.is_file()]
            if parts:
                return composite_hash(parts)

    loader = LOADER_SCRIPT_MAP.get(source_name)
    if loader and loader.exists():
        return "code:" + file_sha256(loader)

    return None


def main():
    parser = argparse.ArgumentParser(description="Backfill sha256 hashes for source imports")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    missing = conn.execute(
        "SELECT import_run_id, source_name, source_version FROM source_import_runs WHERE sha256 IS NULL"
    ).fetchall()

    print(f"Found {len(missing)} imports missing sha256 hashes\n")

    updated = 0
    for row in missing:
        rid = row["import_run_id"]
        name = row["source_name"]
        version = row["source_version"]

        h = compute_hash_for_source(name)
        status = "hashed" if h and not h.startswith("code:") else "code-hash" if h else "no-source-file"

        print(f"  [{rid}] {name} ({version}): {status} → {h or '(skipped)'}")

        if h and not args.dry_run:
            conn.execute("UPDATE source_import_runs SET sha256 = ? WHERE import_run_id = ?", (h, rid))
            updated += 1

    if not args.dry_run:
        conn.commit()

    print(f"\nUpdated {updated} of {len(missing)} imports")
    conn.close()


if __name__ == "__main__":
    main()
