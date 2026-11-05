#!/usr/bin/env python3
"""Derive cell-type-specific regulatory edges from scRNA-seq data.

For each cell-type cluster in the scRNA-seq data, identifies TF-target
edges that are active in that cell type based on:
  1. Both TF and target are expressed in the cluster
  2. The edge exists in the atlas interactions table
  3. TF activity score (regulon overlap with cluster expression)

Stores cell-type-resolved edges in a separate table so the atlas can
report which regulatory relationships are active in which cell types.

Usage:
    python backend/scripts/derive_celltype_regulation.py --species human
    python backend/scripts/derive_celltype_regulation.py --species all
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB_PATH = REPO / "data" / "grn.sqlite3"

MIN_EXPRESSION = 0.1
MIN_CONFIDENCE = 0.3


def derive_for_species(conn: sqlite3.Connection, species: str) -> dict:
    dataset_id = f"scrna_{species}"

    ds = conn.execute(
        "SELECT n_clusters FROM scrna_datasets WHERE dataset_id = ?", (dataset_id,)
    ).fetchone()
    if not ds:
        return {"species": species, "error": "no scRNA-seq data"}

    clusters = conn.execute(
        "SELECT cluster_id, cluster_name, n_cells FROM scrna_clusters WHERE dataset_id = ?",
        (dataset_id,)
    ).fetchall()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS celltype_regulatory_edges (
            dataset_id   TEXT NOT NULL,
            cluster_id   TEXT NOT NULL,
            source_id    TEXT NOT NULL,
            target_id    TEXT NOT NULL,
            confidence   REAL NOT NULL,
            regulation_type TEXT,
            tf_expression    REAL,
            target_expression REAL,
            activity_score   REAL,
            PRIMARY KEY (dataset_id, cluster_id, source_id, target_id)
        )
    """)

    conn.execute("DELETE FROM celltype_regulatory_edges WHERE dataset_id = ?", (dataset_id,))

    total_edges = 0
    cluster_stats = []

    for cluster_id, cluster_name, n_cells in clusters:
        expressed = {}
        for gene_id, mean_expr in conn.execute(
            "SELECT gene_id, mean_expression FROM scrna_cluster_expression "
            "WHERE dataset_id = ? AND cluster_id = ? AND mean_expression >= ?",
            (dataset_id, cluster_id, MIN_EXPRESSION),
        ).fetchall():
            expressed[gene_id] = mean_expr

        if not expressed:
            continue

        gene_set = set(expressed)
        gene_list = list(gene_set)
        edges = []
        batch_size = 500
        for batch_start in range(0, len(gene_list), batch_size):
            batch = gene_list[batch_start:batch_start + batch_size]
            placeholders = ",".join("?" * len(batch))
            batch_edges = conn.execute(
                f"SELECT source_id, target_id, confidence, regulation_type "
                f"FROM interactions "
                f"WHERE source_id IN ({placeholders}) "
                f"AND confidence >= ?",
                batch + [MIN_CONFIDENCE]
            ).fetchall()
            edges.extend(batch_edges)

        cluster_edges = []
        for src, tgt, conf, reg in edges:
            if src in gene_set and tgt in gene_set:
                tf_expr = expressed.get(src, 0.0)
                tgt_expr = expressed.get(tgt, 0.0)
                activity = conf * (tf_expr * tgt_expr) ** 0.5
                cluster_edges.append((
                    dataset_id, cluster_id, src, tgt,
                    round(conf, 4), reg, round(tf_expr, 4),
                    round(tgt_expr, 4), round(activity, 4),
                ))

        if cluster_edges:
            conn.executemany(
                "INSERT OR IGNORE INTO celltype_regulatory_edges "
                "(dataset_id, cluster_id, source_id, target_id, confidence, "
                " regulation_type, tf_expression, target_expression, activity_score) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                cluster_edges,
            )
            total_edges += len(cluster_edges)

        tfs_in_cluster = len({e[2] for e in cluster_edges})
        cluster_stats.append({
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
            "n_cells": n_cells,
            "n_expressed": len(expressed),
            "n_edges": len(cluster_edges),
            "n_tfs": tfs_in_cluster,
        })

    conn.commit()

    return {
        "species": species,
        "dataset_id": dataset_id,
        "n_clusters": len(clusters),
        "total_celltype_edges": total_edges,
        "cluster_stats": cluster_stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--species", required=True)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    if args.species == "all":
        species_list = [r[0] for r in conn.execute(
            "SELECT DISTINCT species FROM scrna_datasets"
        ).fetchall()]
    else:
        species_list = [args.species]

    for species in species_list:
        print(f"\nDeriving cell-type regulation for {species}...")
        result = derive_for_species(conn, species)
        if "error" in result:
            print(f"  Skipped: {result['error']}")
            continue
        print(f"  {result['total_celltype_edges']:,} cell-type edges across "
              f"{result['n_clusters']} clusters")
        for cs in result["cluster_stats"]:
            print(f"    {cs['cluster_name']}: {cs['n_edges']:,} edges, "
                  f"{cs['n_tfs']} TFs, {cs['n_expressed']:,} genes")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
