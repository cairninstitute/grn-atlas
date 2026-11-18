#!/usr/bin/env python3
"""Assess whether orthology-transferred edges have independent evidence in the recipient species."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"
DB = BACKEND / "data" / "grn.sqlite3"

PLANT_SPECIES = ["arabidopsis", "tomato", "petunia", "rice", "pepper", "potato"]


def output(data):
    print(json.dumps(data, indent=2, default=str))


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0] > 0


def species_summary(conn: sqlite3.Connection, species: str, min_cis: float) -> dict:
    projected = conn.execute(
        """SELECT COUNT(*) FROM interactions i
           JOIN genes s ON s.id = i.source_id
           WHERE s.species = ? AND i.sources LIKE '%Inferred:%'""",
        (species,),
    ).fetchone()[0]

    if projected == 0:
        return {
            "species": species,
            "projected_edges": 0,
            "cis_supported": 0,
            "cis_support_rate": None,
            "summary": f"No projected edges found for {species}.",
        }

    if not table_exists(conn, "cis_support_scores"):
        return {
            "species": species,
            "projected_edges": projected,
            "scored_edges": 0,
            "cis_supported": 0,
            "cis_support_rate": None,
            "summary": (
                f"{projected} projected edges in {species} but cis_support_scores "
                f"table does not exist. Run score_cis_support.py first."
            ),
        }

    cis_supported = conn.execute(
        "SELECT COUNT(*) FROM cis_support_scores WHERE species=? AND cis_score >= ?",
        (species, min_cis),
    ).fetchone()[0]

    total_scored = conn.execute(
        "SELECT COUNT(*) FROM cis_support_scores WHERE species=?",
        (species,),
    ).fetchone()[0]

    rate = round(cis_supported / max(total_scored, 1), 4)

    return {
        "species": species,
        "projected_edges": projected,
        "scored_edges": total_scored,
        "cis_supported": cis_supported,
        "cis_support_rate": rate,
        "summary": (
            f"{cis_supported}/{total_scored} scored edges ({rate:.1%}) have cis-regulatory "
            f"motif support in {species} (threshold >= {min_cis})."
        ),
    }


def edge_detail(conn: sqlite3.Connection, source_id: str, target_id: str) -> dict:
    row = None
    if table_exists(conn, "cis_support_scores"):
        row = conn.execute(
            """SELECT species, has_motif_hit, best_motif_score, best_motif_pvalue,
                      motif_id, hit_count, cis_score
               FROM cis_support_scores
               WHERE source_id=? AND target_id=?""",
            (source_id, target_id),
        ).fetchone()

    interaction = conn.execute(
        "SELECT confidence, sign, sources FROM interactions WHERE source_id=? AND target_id=?",
        (source_id, target_id),
    ).fetchone()

    if row is None and interaction is None:
        return {"error": f"No edge found between {source_id} and {target_id}."}

    result = {
        "source_id": source_id,
        "target_id": target_id,
    }

    if interaction:
        try:
            sources = json.loads(interaction[2])
        except (json.JSONDecodeError, TypeError):
            sources = []
        is_projected = any("Inferred:" in s for s in sources)
        result["confidence"] = interaction[0]
        result["sign"] = interaction[1]
        result["is_projected"] = is_projected
        result["sources"] = sources

    if row:
        result["cis_support"] = {
            "species": row[0],
            "has_motif_hit": bool(row[1]),
            "best_motif_score": row[2],
            "best_motif_pvalue": row[3],
            "motif_id": row[4],
            "hit_count": row[5],
            "cis_score": row[6],
        }
    else:
        result["cis_support"] = None
        result["note"] = "No cis-support score computed for this edge. Run score_cis_support.py first."

    return result


def tf_projected_targets(conn: sqlite3.Connection, source_id: str, species: str,
                         min_cis: float) -> dict:
    rows = []
    if table_exists(conn, "cis_support_scores"):
        rows = conn.execute(
            """SELECT c.target_id, c.has_motif_hit, c.best_motif_score, c.motif_id,
                      c.hit_count, c.cis_score, i.confidence, i.sign
               FROM cis_support_scores c
               JOIN interactions i ON i.source_id = c.source_id AND i.target_id = c.target_id
               WHERE c.source_id = ? AND c.species = ?
               ORDER BY c.cis_score DESC""",
            (source_id, species),
        ).fetchall()

    if not rows:
        all_targets = conn.execute(
            """SELECT i.target_id FROM interactions i
               JOIN genes s ON s.id = i.source_id
               WHERE i.source_id = ? AND s.species = ? AND i.sources LIKE '%Inferred:%'""",
            (source_id, species),
        ).fetchall()
        return {
            "source_id": source_id,
            "species": species,
            "projected_targets": len(all_targets),
            "scored_targets": 0,
            "cis_supported": 0,
            "edges": [],
            "note": "No cis-support scores found. Run score_cis_support.py first.",
        }

    edges = []
    supported = 0
    for target_id, has_hit, score, motif, hits, cis, conf, sign in rows:
        if cis >= min_cis:
            supported += 1
        edges.append({
            "target_id": target_id,
            "has_motif_hit": bool(has_hit),
            "best_motif_score": score,
            "motif_id": motif,
            "hit_count": hits,
            "cis_score": cis,
            "confidence": conf,
            "sign": sign,
        })

    rate = round(supported / max(len(rows), 1), 4)
    return {
        "source_id": source_id,
        "species": species,
        "scored_targets": len(rows),
        "cis_supported": supported,
        "cis_support_rate": rate,
        "edges": edges,
        "summary": (
            f"{supported}/{len(rows)} projected targets of {source_id} in {species} "
            f"({rate:.1%}) have cis-regulatory motif support."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--species", default=None)
    parser.add_argument("--source-id", default=None)
    parser.add_argument("--target-id", default=None)
    parser.add_argument("--all", action="store_true", help="Summary across all plant species")
    parser.add_argument("--min-cis-score", type=float, default=0.3)
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)

    if args.source_id and args.target_id:
        output(edge_detail(conn, args.source_id, args.target_id))
    elif args.source_id and args.species:
        output(tf_projected_targets(conn, args.source_id, args.species, args.min_cis_score))
    elif args.all:
        results = {}
        for sp in PLANT_SPECIES:
            results[sp] = species_summary(conn, sp, args.min_cis_score)
        total_proj = sum(r["projected_edges"] for r in results.values())
        total_sup = sum(r["cis_supported"] for r in results.values())
        total_scored = sum(r.get("scored_edges", 0) for r in results.values())
        output({
            "species_summaries": results,
            "total_projected": total_proj,
            "total_scored": total_scored,
            "total_cis_supported": total_sup,
            "overall_rate": round(total_sup / max(total_scored, 1), 4) if total_scored else None,
        })
    elif args.species:
        output(species_summary(conn, args.species, args.min_cis_score))
    else:
        output({"error": "Provide --species, --source-id/--target-id, or --all."})

    conn.close()


if __name__ == "__main__":
    main()
