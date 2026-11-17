#!/usr/bin/env python3
"""Audit which sources and evidence tiers feed the observed signed graph.

The observed graph that feedback-control and the skills reason over is every
interaction whose sign_evidence is in the default tiers. Nothing filters on
which source supplied the sign, so this audit reports what is actually in
there, per source and per tier.

Read-only: opens the database with mode=ro and runs only SELECTs, so it is
safe alongside a running backend.

Output is stable-ordered and intended to be committed and diffed between
builds; a change in these numbers is a change in what the atlas asserts.

Usage:
    venv/bin/python backend/scripts/audit_evidence_tiers.py
    venv/bin/python backend/scripts/audit_evidence_tiers.py --species arabidopsis
    venv/bin/python backend/scripts/audit_evidence_tiers.py --report path/to.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
REPORT = BACKEND / "data" / "evidence_tier_audit.json"

DEFAULT_TIERS = ("measured", "perturbation")
DEFAULT_MIN_CONFIDENCE = 0.5


def rows(conn: sqlite3.Connection, sql: str, params: dict | None = None) -> list[dict]:
    cur = conn.execute(sql, params or {})
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--species", default=None,
                    help="restrict the per-source breakdown to one species")
    ap.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE,
                    help="matches the feedback-control default")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"database missing: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    tiers = ",".join(f"'{t}'" for t in DEFAULT_TIERS)
    in_graph = (f"i.sign IS NOT NULL AND i.sign_evidence IN ({tiers}) "
                f"AND i.confidence >= :min_conf")
    p = {"min_conf": args.min_confidence}
    species_clause = ""
    if args.species:
        species_clause = "AND s.species = :species"
        p["species"] = args.species

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(args.db.resolve()),
        "default_tiers": list(DEFAULT_TIERS),
        "min_confidence": args.min_confidence,
        "species_filter": args.species,
        "results": {},
        "failures": [],
    }

    report["results"]["graph_sources"] = rows(conn, f"""
        SELECT s.species AS species, je.value AS source_name,
               i.sign_evidence AS tier, COUNT(*) AS edges
        FROM interactions i, json_each(i.sources) je, genes s, genes t
        WHERE s.id = i.source_id AND t.id = i.target_id
          AND s.species = t.species {species_clause}
          AND {in_graph}
        GROUP BY s.species, je.value, i.sign_evidence
        ORDER BY species, edges DESC, source_name""", p)

    report["results"]["single_source_edges"] = rows(conn, f"""
        SELECT s.species AS species, i.sources AS sources, COUNT(*) AS edges
        FROM interactions i, genes s, genes t
        WHERE s.id = i.source_id AND t.id = i.target_id
          AND s.species = t.species {species_clause}
          AND json_array_length(i.sources) = 1
          AND {in_graph}
        GROUP BY s.species, i.sources
        ORDER BY edges DESC, species, sources LIMIT 40""", p)

    report["results"]["projected_edges_by_tier"] = rows(conn, """
        SELECT s.species AS species, i.sign_evidence AS tier, COUNT(*) AS edges
        FROM interactions i, genes s
        WHERE s.id = i.source_id
          AND i.sources LIKE '%Inferred:%'
          AND i.sign IS NOT NULL
        GROUP BY s.species, i.sign_evidence
        ORDER BY edges DESC, species""")

    report["results"]["perturbation_signs_by_class"] = rows(conn, """
        SELECT s.species AS species, i.sign AS relation_type, COUNT(*) AS edges
        FROM interactions i, genes s, genes t
        WHERE s.id = i.source_id AND t.id = i.target_id
          AND s.species = t.species
          AND i.sign_evidence = 'perturbation'
        GROUP BY s.species, i.sign
        ORDER BY species, relation_type""")

    report["results"]["sign_evidence_totals"] = rows(conn, """
        SELECT COALESCE(sign_evidence, '(null)') AS tier, COUNT(*) AS edges
        FROM interactions GROUP BY sign_evidence ORDER BY edges DESC, tier""")

    report["results"]["headline_counts"] = rows(conn, """
        SELECT (SELECT COUNT(*) FROM genes) AS genes,
               (SELECT COUNT(*) FROM interactions) AS interactions""")

    try:
        report["results"]["multilayer_edges"] = rows(conn, """
            SELECT species, regulatory_layer, COUNT(*) AS edges
            FROM regulatory_layer_edges
            GROUP BY species, regulatory_layer
            ORDER BY edges DESC, species, regulatory_layer""")
    except sqlite3.Error as exc:
        report["results"]["multilayer_edges"] = []
        report["failures"].append(f"regulatory_layer_edges unavailable: {exc}")

    # Cross-check the calibration gate against what is actually in the graph.
    try:
        gates = rows(conn, """
            SELECT species, relation_type, cases, precision, gate_pass
            FROM perturbation_sign_calibration
            ORDER BY species, relation_type""")
        report["results"]["calibration_gates"] = gates
        passing = {(g["species"], g["relation_type"]) for g in gates if g["gate_pass"]}
        for row in report["results"]["perturbation_signs_by_class"]:
            key = (row["species"], row["relation_type"])
            if key not in passing and row["edges"]:
                report["failures"].append(
                    f"ungated perturbation signs in the observed graph: "
                    f"{row['species']}/{row['relation_type']} = {row['edges']:,} edges")
    except sqlite3.Error as exc:
        report["failures"].append(f"perturbation_sign_calibration unavailable: {exc}")

    conn.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")

    print(f"\nEvidence-tier audit   {report['generated_at'][:19]}Z")
    print(f"tiers={list(DEFAULT_TIERS)}  min_confidence={args.min_confidence}\n")
    for name, res in report["results"].items():
        print(f"--- {name}  ({len(res)} rows)")
        for r in res[:12]:
            print("    " + "  ".join(f"{k}={v}" for k, v in r.items()))
        if len(res) > 12:
            print(f"    ... {len(res) - 12} more (full set in the report)")
        print()
    if report["failures"]:
        print("FAILURES")
        for f in report["failures"]:
            print(f"  - {f}")
        print()
    print(f"Report: {args.report}")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
