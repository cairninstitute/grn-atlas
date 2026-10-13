#!/usr/bin/env python3
"""Audit ConnecTF source files, mapped pairs, and database endpoint integrity."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_connectf import load_species_edges, parse_metadata  # noqa: E402


def audit_species(conn: sqlite3.Connection, root: Path, species: str) -> dict:
    genes = {row[0] for row in conn.execute("SELECT id FROM genes WHERE species=?", (species,))}
    data_dir = root / species / "data"
    metadata_dir = root / species / "metadata"
    data_files = [path for path in data_dir.glob("*.csv") if not path.name.startswith("._")]
    metadata = parse_metadata(metadata_dir)
    parsed = load_species_edges(data_dir, metadata_dir, genes, species)
    db_rows = conn.execute(
        "SELECT i.source_id, i.target_id, i.regulation_type, gs.id, gt.id "
        "FROM interactions i "
        "LEFT JOIN genes gs ON gs.id=i.source_id "
        "LEFT JOIN genes gt ON gt.id=i.target_id "
        "WHERE i.sources LIKE '%ConnecTF%' AND gs.species=?",
        (species,),
    ).fetchall()
    parsed_pairs = {(row[0], row[1]) for row in parsed}
    db_pairs = {(row[0], row[1]) for row in db_rows}
    return {
        "species": species,
        "atlas_genes": len(genes),
        "data_files": len(data_files),
        "metadata_records": len(metadata),
        "parsed_unique_pairs": len(parsed_pairs),
        "database_pairs": len(db_pairs),
        "signed_database_pairs": sum(row[2] in ("activation", "repression") for row in db_rows),
        "missing_from_database": len(parsed_pairs - db_pairs),
        "database_not_reproduced": len(db_pairs - parsed_pairs),
        "missing_source_endpoints": sum(row[3] is None for row in db_rows),
        "missing_target_endpoints": sum(row[4] is None for row in db_rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--db", type=Path, default=BACKEND / "data" / "grn.sqlite3")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        report = [audit_species(conn, args.root, species) for species in ("arabidopsis", "rice")]
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    return 1 if any(row["missing_from_database"] or row["missing_source_endpoints"] or
                    row["missing_target_endpoints"] for row in report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
