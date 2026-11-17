#!/usr/bin/env python3
"""Audit how much of the atlas carries a regulatory sign, and what could.

Separates three different questions that are easy to conflate:

  1. How much is signed, and how much of the unsigned bulk is binding or
     prediction evidence that carries no direction in principle.
  2. How many unsigned edges have perturbation observations behind them, and
     how many of those meet the replication rule the consensus pipeline uses.
  3. How many unsigned edges already have a signed record in
     regulatory_evidence, broken out by the source and evidence layer that
     supplies it - because a perturbation_signed/downstream record is not the
     same claim as a curated direct sign.

Read-only: opens the database with mode=ro and runs only SELECTs, plus TEMP
tables held outside the database file.

Output is stable-ordered and intended to be committed and diffed between
builds.

Usage:
    venv/bin/python backend/scripts/audit_sign_coverage.py
    venv/bin/python backend/scripts/audit_sign_coverage.py --report path/to.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
REPORT = BACKEND / "data" / "sign_coverage_audit.json"

UNSIGNED = "(i.sign IS NULL OR i.sign_evidence = 'unknown')"


def rows(conn: sqlite3.Connection, sql: str, params: dict | None = None) -> list[dict]:
    cur = conn.execute(sql, params or {})
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--quick", action="store_true",
                    help="skip the full-table scans; coverage totals only")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"database missing: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(args.db.resolve()),
        "results": {},
        "timings_seconds": {},
        "notes": [],
    }

    def step(name, sql, params=None, build=()):
        t0 = time.time()
        try:
            for stmt in build:
                conn.execute(stmt)
            report["results"][name] = rows(conn, sql, params)
        except sqlite3.Error as exc:
            report["results"][name] = []
            report["notes"].append(f"{name}: {exc}")
        report["timings_seconds"][name] = round(time.time() - t0, 1)
        print(f"  {name} ({report['timings_seconds'][name]}s)", flush=True)

    print("Coverage totals...", flush=True)
    step("coverage_by_species_and_tier", f"""
        SELECT g.species AS species,
               CASE WHEN {UNSIGNED} THEN 'unsigned' ELSE i.sign_evidence END AS tier,
               COUNT(*) AS edges
        FROM interactions i, genes g
        WHERE g.id = i.source_id
        GROUP BY g.species, tier
        ORDER BY species, edges DESC, tier""")

    if args.quick:
        conn.close()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nReport: {args.report}")
        return 0

    print("Unsigned bulk...", flush=True)
    step("unsigned_by_source", f"""
        SELECT je.value AS source_name, COUNT(*) AS edges
        FROM interactions i, json_each(i.sources) je
        WHERE {UNSIGNED}
        GROUP BY je.value ORDER BY edges DESC, source_name""")

    step("unsigned_by_confidence", f"""
        SELECT CASE WHEN i.confidence >= 0.8 THEN 'a >=0.8'
                    WHEN i.confidence >= 0.6 THEN 'b 0.6-0.8'
                    WHEN i.confidence >= 0.5 THEN 'c 0.5-0.6'
                    ELSE 'd <0.5' END AS confidence_band,
               COUNT(*) AS edges
        FROM interactions i WHERE {UNSIGNED}
        GROUP BY confidence_band ORDER BY confidence_band""")

    print("Perturbation headroom...", flush=True)
    step("perturbation_headroom", f"""
        SELECT COUNT(*) AS unsigned_with_any_observation,
               SUM(CASE WHEN o.experiments >= 2 THEN 1 ELSE 0 END) AS meets_replication_rule,
               SUM(CASE WHEN o.experiments = 1 THEN 1 ELSE 0 END) AS single_experiment_only,
               SUM(CASE WHEN o.significant_obs > 0 THEN 1 ELSE 0 END) AS has_significant_observation
        FROM interactions i JOIN temp.obs o
          ON o.s = i.source_id AND o.t = i.target_id
        WHERE {UNSIGNED}""", build=("""
        CREATE TEMP TABLE obs AS
        SELECT perturbed_gene AS s, affected_gene AS t,
               COUNT(DISTINCT COALESCE(experiment_id, dataset_label)) AS experiments,
               SUM(CASE WHEN observed_significant = 1 THEN 1 ELSE 0 END) AS significant_obs
        FROM perturbation_observations
        GROUP BY perturbed_gene, affected_gene""",
        "CREATE INDEX temp.ix_obs ON obs(s, t)"))

    step("perturbation_pair_coverage", """
        SELECT (SELECT COUNT(*) FROM temp.obs) AS distinct_observation_pairs,
               (SELECT COUNT(*) FROM temp.obs o WHERE EXISTS
                  (SELECT 1 FROM interactions i
                    WHERE i.source_id = o.s AND i.target_id = o.t))
                 AS pairs_present_as_edges""")

    print("Signed-evidence headroom...", flush=True)
    step("signed_evidence_headroom", f"""
        SELECT COUNT(DISTINCT e.s || '>' || e.t) AS unsigned_with_signed_evidence,
               COUNT(DISTINCT CASE WHEN e.layer = 'direct_signed' AND e.direct = 'direct'
                     THEN e.s || '>' || e.t END) AS from_curated_direct_evidence,
               COUNT(DISTINCT CASE WHEN e.layer = 'perturbation_signed'
                     THEN e.s || '>' || e.t END) AS from_perturbation_evidence
        FROM temp.sev e JOIN interactions i
          ON i.source_id = e.s AND i.target_id = e.t
        WHERE {UNSIGNED}""",
        build=("""
        CREATE TEMP TABLE sev AS
        SELECT source_id AS s, target_id AS t, source_name AS src,
               relation_type AS rel, evidence_layer AS layer,
               directness AS direct, species AS sp
        FROM regulatory_evidence
        WHERE relation_type IN ('activation','repression')""",
        "CREATE INDEX temp.ix_sev ON sev(s, t)"))

    step("signed_evidence_by_source", f"""
        SELECT e.sp AS species, e.src AS source_name, e.layer AS evidence_layer,
               e.direct AS directness,
               COUNT(DISTINCT e.s || '>' || e.t) AS unsigned_edges_it_could_sign
        FROM temp.sev e JOIN interactions i
          ON i.source_id = e.s AND i.target_id = e.t
        WHERE {UNSIGNED}
        GROUP BY e.sp, e.src, e.layer, e.direct
        ORDER BY unsigned_edges_it_could_sign DESC, species, source_name""")

    step("signed_evidence_inventory", """
        SELECT src AS source_name, layer AS evidence_layer, COUNT(*) AS records
        FROM temp.sev GROUP BY src, layer
        ORDER BY records DESC, source_name""")

    # Derived summary: the only honest headline.
    cov = report["results"].get("coverage_by_species_and_tier", [])
    signed = sum(r["edges"] for r in cov if r["tier"] != "unsigned")
    unsigned = sum(r["edges"] for r in cov if r["tier"] == "unsigned")
    by_src = report["results"].get("signed_evidence_by_source", [])
    curated = sum(r["unsigned_edges_it_could_sign"] for r in by_src
                  if r["evidence_layer"] == "direct_signed" and r["directness"] == "direct")
    report["summary"] = {
        "signed_edges": signed,
        "unsigned_edges": unsigned,
        "signed_fraction": round(signed / (signed + unsigned), 4) if signed + unsigned else None,
        "recoverable_from_curated_direct_evidence": curated,
        "signed_fraction_if_recovered":
            round((signed + curated) / (signed + unsigned), 4) if signed + unsigned else None,
    }
    report["notes"].append(
        "recoverable_from_curated_direct_evidence counts only evidence_layer="
        "'direct_signed' with directness='direct'. perturbation_signed/downstream "
        "records are excluded: they are single-experiment downstream responses, "
        "the class that failed calibration.")

    conn.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")

    s = report["summary"]
    print(f"\nSigned: {s['signed_edges']:,}   Unsigned: {s['unsigned_edges']:,}   "
          f"({s['signed_fraction']:.1%} signed)")
    print(f"Recoverable from curated direct evidence: "
          f"{s['recoverable_from_curated_direct_evidence']:,} "
          f"-> {s['signed_fraction_if_recovered']:.1%}")
    print(f"\nReport: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
