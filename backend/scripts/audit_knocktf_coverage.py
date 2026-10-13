#!/usr/bin/env python3
"""Summarize loaded KnockTF coverage and local source-file integrity."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import file_sha256  # noqa: E402

DEFAULT_FILES = {
    "arabidopsis": Path("/tmp/knocktf_arabidopsis.txt"),
    "human": Path("/tmp/knocktf_human.txt"),
    "mouse": Path("/tmp/knocktf_mouse.txt"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=BACKEND / "data" / "grn.sqlite3")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        rows = conn.execute(
            "SELECT species, COUNT(*), COUNT(DISTINCT perturbed_gene), "
            "COUNT(DISTINCT affected_gene) FROM perturbation_observations "
            "WHERE dataset_label='knocktf' GROUP BY species ORDER BY species"
        ).fetchall()
    report = []
    for species, observations, regulators, affected_genes in rows:
        path = DEFAULT_FILES.get(species)
        report.append({
            "species": species,
            "observations": observations,
            "perturbed_regulators": regulators,
            "affected_genes": affected_genes,
            "source_file_bytes": path.stat().st_size if path and path.exists() else None,
            "source_file_sha256": file_sha256(path) if path and path.exists() else None,
        })
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
