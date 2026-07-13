#!/usr/bin/env python3
"""CLI for grn-infer skill — query inferred regulatory edges."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
DB_PATH = REPO / "backend" / "data" / "grn.sqlite3"


def direct_query(args):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    species = args.species.lower()
    gene_id = args.gene_id

    if gene_id:
        row = conn.execute("SELECT id FROM genes WHERE id = ?", (gene_id,)).fetchone()
        if not row:
            row = conn.execute(
                "SELECT id FROM genes WHERE symbol = ? COLLATE NOCASE AND species = ?",
                (gene_id, species)).fetchone()
        if row:
            gene_id = row["id"]

    conditions = ["ie.species = ?"]
    params = [species]

    if gene_id:
        if args.direction == "regulators":
            conditions.append("ie.target_id = ?")
            params.append(gene_id)
        elif args.direction == "targets":
            conditions.append("ie.source_id = ?")
            params.append(gene_id)
        else:
            conditions.append("(ie.source_id = ? OR ie.target_id = ?)")
            params.extend([gene_id, gene_id])

    if args.method:
        conditions.append("ie.method = ?")
        params.append(args.method)

    conditions.append("ie.importance >= ?")
    params.append(args.min_importance)

    where = " AND ".join(conditions)
    params.append(args.top)

    sql = f"""
        SELECT ie.source_id, gs.symbol AS source_symbol,
               ie.target_id, gt.symbol AS target_symbol,
               ie.importance, ie.method
        FROM inferred_edges ie
        JOIN genes gs ON gs.id = ie.source_id
        JOIN genes gt ON gt.id = ie.target_id
        WHERE {where}
        ORDER BY ie.importance DESC
        LIMIT ?
    """
    rows = conn.execute(sql, params).fetchall()

    edges = []
    for r in rows:
        edge = {
            "source_id": r["source_id"],
            "source_symbol": r["source_symbol"],
            "target_id": r["target_id"],
            "target_symbol": r["target_symbol"],
            "importance": round(r["importance"], 4),
            "method": r["method"],
        }
        if args.compare_curated:
            curated = conn.execute(
                "SELECT regulation_type, confidence FROM interactions "
                "WHERE source_id = ? AND target_id = ?",
                (r["source_id"], r["target_id"]),
            ).fetchone()
            edge["has_curated_support"] = curated is not None
            if curated:
                edge["curated_regulation_type"] = curated["regulation_type"]
                edge["curated_confidence"] = curated["confidence"]
        edges.append(edge)

    total = conn.execute(
        f"SELECT COUNT(*) FROM inferred_edges ie WHERE {where}",
        params[:-1],
    ).fetchone()[0]

    conn.close()
    return {
        "species": species,
        "gene_id": gene_id,
        "method": args.method or "all",
        "min_importance": args.min_importance,
        "edges": edges,
        "returned": len(edges),
        "total_available": total,
        "note": "Computationally inferred edges, not experimentally validated.",
    }


def http_query(args):
    import urllib.request
    body = {"species": args.species, "min_importance": args.min_importance, "top": args.top}
    if args.gene_id:
        body["gene_id"] = args.gene_id
    if args.direction != "both":
        body["direction"] = args.direction
    if args.method:
        body["method"] = args.method
    if args.compare_curated:
        body["compare_curated"] = True

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{args.http}/api/v1/inferred-edges",
        data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    p = argparse.ArgumentParser(description="Query inferred regulatory edges")
    p.add_argument("--species", required=True)
    p.add_argument("--gene-id", default=None)
    p.add_argument("--direction", choices=["regulators", "targets", "both"], default="both")
    p.add_argument("--method", default=None, help="GRNBoost2 or GENIE3")
    p.add_argument("--min-importance", type=float, default=0.01)
    p.add_argument("--compare-curated", action="store_true")
    p.add_argument("--top", type=int, default=50)
    p.add_argument("--http", default=None, help="Base URL for HTTP mode")
    args = p.parse_args()

    result = http_query(args) if args.http else direct_query(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
