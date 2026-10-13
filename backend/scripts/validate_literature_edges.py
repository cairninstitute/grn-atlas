#!/usr/bin/env python3
"""Validate PMID-backed signed literature edge files before database rebuilds."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"


def validate_file(path: Path, species: str, genes: set[str]) -> dict:
    counts = Counter()
    errors = []
    seen = set()
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        counts["records"] += 1
        parts = line.split("\t")
        if len(parts) < 5:
            errors.append(f"{path.name}:{line_number}: expected 5 columns")
            continue
        source, target, relation, confidence, citation = parts[:5]
        if relation not in {"activation", "repression"}:
            errors.append(f"{path.name}:{line_number}: relation must be activation or repression")
        try:
            value = float(confidence)
            if not 0 <= value <= 1:
                raise ValueError
        except ValueError:
            errors.append(f"{path.name}:{line_number}: confidence must be between 0 and 1")
        citation_ids = citation.split(":", 1)[1].split(",") if citation.startswith("literature:") else []
        if not citation_ids or not all(value.strip().isdigit() for value in citation_ids):
            errors.append(f"{path.name}:{line_number}: citation must be literature:<PMID>")
        for role, gene in (("source", source), ("target", target)):
            if gene not in genes:
                errors.append(f"{path.name}:{line_number}: {role} {gene} is not an atlas {species} gene")
        key = (source, target, relation, citation)
        if key in seen:
            errors.append(f"{path.name}:{line_number}: duplicate record")
        seen.add(key)
    return {"species": species, "file": str(path), "counts": dict(counts), "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DATA / "grn.sqlite3")
    parser.add_argument("--species", nargs="*", default=["tomato", "petunia", "potato", "pepper"])
    args = parser.parse_args()
    reports = []
    with sqlite3.connect(args.db) as conn:
        for species in args.species:
            path = DATA / f"literature_edges_{species}.tsv"
            if not path.exists():
                reports.append({"species": species, "file": str(path), "counts": {},
                                "errors": [], "status": "no_curated_file"})
                continue
            genes = {row[0] for row in conn.execute("SELECT id FROM genes WHERE species=?", (species,))}
            report = validate_file(path, species, genes)
            report["status"] = "pass" if not report["errors"] else "fail"
            reports.append(report)
    print(json.dumps(reports, indent=2))
    return 1 if any(report.get("errors") for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
