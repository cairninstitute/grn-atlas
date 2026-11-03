#!/usr/bin/env python3
"""Query structural binding predictions from the GRN Atlas."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas structural binding predictions")
    common.add_common_args(parser)
    parser.add_argument("--species", help="Species name")
    parser.add_argument("--source-id", help="TF gene ID")
    parser.add_argument("--target-id", help="Target gene ID")
    parser.add_argument("--binding-class", choices=["likely", "uncertain", "unlikely", "no_sequence", "error"])
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--stats", action="store_true", help="Show summary statistics")
    args = parser.parse_args()

    if args.http:
        if args.stats:
            data = common.http_get(args.http, "/api/v1/structural-binding/stats")
        elif args.source_id and args.target_id and args.species:
            data = common.http_get(
                args.http,
                f"/api/v1/structural-binding/{args.species}/{args.source_id}/{args.target_id}",
            )
        else:
            params = {}
            if args.species:
                params["species"] = args.species
            if args.binding_class:
                params["binding_class"] = args.binding_class
            if args.min_confidence > 0:
                params["min_confidence"] = args.min_confidence
            params["limit"] = args.top
            sp = args.species or "all"
            data = common.http_get(args.http, f"/api/v1/structural-binding/{sp}", params=params)
    else:
        import sqlite3
        conn = sqlite3.connect(str(common.DB_PATH))
        conn.row_factory = sqlite3.Row

        if args.stats:
            data = _query_stats(conn)
        elif args.source_id and args.target_id and args.species:
            data = _query_single(conn, args.species, args.source_id, args.target_id)
        else:
            data = _query_list(conn, args.species, args.binding_class,
                               args.min_confidence, args.top)
        conn.close()

    common.output(data)


def _query_stats(conn):
    rows = conn.execute("""
        SELECT species, binding_class, COUNT(*) as count,
               AVG(confidence_score) as avg_confidence
        FROM structural_binding_predictions
        GROUP BY species, binding_class
        ORDER BY species, binding_class
    """).fetchall()
    if not rows:
        return {"message": "No structural binding predictions found. Run predict_structural_binding.py first."}
    stats = {}
    for r in rows:
        sp = r["species"]
        if sp not in stats:
            stats[sp] = {}
        stats[sp][r["binding_class"]] = {
            "count": r["count"],
            "avg_confidence": round(r["avg_confidence"], 4) if r["avg_confidence"] else None,
        }
    return {"stats": stats}


def _query_single(conn, species, source_id, target_id):
    row = conn.execute("""
        SELECT sbp.*, gs.symbol as source_symbol, gt.symbol as target_symbol
        FROM structural_binding_predictions sbp
        LEFT JOIN genes gs ON gs.id = sbp.source_id
        LEFT JOIN genes gt ON gt.id = sbp.target_id
        WHERE sbp.species = ? AND sbp.source_id = ? AND sbp.target_id = ?
    """, (species, source_id, target_id)).fetchone()
    if not row:
        return {"message": "No prediction found for this edge."}
    return dict(row)


def _query_list(conn, species, binding_class, min_confidence, limit):
    clauses = []
    params = []
    if species:
        clauses.append("sbp.species = ?")
        params.append(species)
    if binding_class:
        clauses.append("sbp.binding_class = ?")
        params.append(binding_class)
    if min_confidence > 0:
        clauses.append("sbp.confidence_score >= ?")
        params.append(min_confidence)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    rows = conn.execute(f"""
        SELECT sbp.species, sbp.source_id, sbp.target_id, sbp.relation_type,
               sbp.confidence_score, sbp.binding_class,
               sbp.protein_length, sbp.dna_length, sbp.predicted_at,
               gs.symbol as source_symbol, gt.symbol as target_symbol
        FROM structural_binding_predictions sbp
        LEFT JOIN genes gs ON gs.id = sbp.source_id
        LEFT JOIN genes gt ON gt.id = sbp.target_id
        {where}
        ORDER BY sbp.confidence_score DESC NULLS LAST
        LIMIT ?
    """, params).fetchall()
    return {"predictions": [dict(r) for r in rows], "count": len(rows)}


if __name__ == "__main__":
    main()
