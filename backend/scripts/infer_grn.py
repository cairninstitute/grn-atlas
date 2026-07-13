#!/usr/bin/env python3
"""Infer regulatory edges from expression data using GRNBoost2 and/or GENIE3.

Implements the core algorithms directly using sklearn, parallelized with joblib.
GRNBoost2 = gradient boosting per target gene; GENIE3 = random forest per target.

Usage:
    backend/venv/bin/python backend/scripts/infer_grn.py --all
    backend/venv/bin/python backend/scripts/infer_grn.py --species arabidopsis --method grnboost2
"""
import argparse
import gzip
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

sys.path.insert(0, str(REPO))
from expression import get_matrix, species_with_expression

# Tuned for small sample sizes (18-29 samples)
GRNBOOST2_PARAMS = {
    "n_estimators": 100,
    "max_features": 0.5,
    "learning_rate": 0.05,
    "subsample": 0.9,
    "max_depth": 2,
}

GENIE3_PARAMS = {
    "n_estimators": 200,
    "max_features": "sqrt",
}


def get_tf_list(species: str) -> list[str]:
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT id FROM genes WHERE species = ? AND is_tf = 1", (species,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _fit_one_target(target_idx, expr_matrix, tf_indices, gene_names, method, seed):
    predictor_indices = [i for i in tf_indices if i != target_idx]
    if not predictor_indices:
        return []

    X = expr_matrix[:, predictor_indices]
    y = expr_matrix[:, target_idx]

    if np.std(y) == 0:
        return []

    rng = np.random.RandomState(seed + target_idx)
    if method == "grnboost2":
        model = GradientBoostingRegressor(random_state=rng, **GRNBOOST2_PARAMS)
    else:
        model = RandomForestRegressor(random_state=rng, n_jobs=1, **GENIE3_PARAMS)

    model.fit(X, y)
    importances = model.feature_importances_

    target_name = gene_names[target_idx]
    edges = []
    for i, imp in enumerate(importances):
        if imp > 1e-6:
            edges.append((gene_names[predictor_indices[i]], target_name, float(imp)))
    return edges


def run_inference(species: str, method: str, top_edges: int, seed: int,
                  n_jobs: int = -1) -> list[dict]:
    mat = get_matrix(species)
    if mat is None:
        print(f"  Skipping {species}: no expression matrix")
        return []

    tf_ids = get_tf_list(species)
    gene_names = list(mat.genes.keys())
    tf_set = set(tf_ids)
    tf_indices = [i for i, g in enumerate(gene_names) if g in tf_set]

    if not tf_indices:
        print(f"  Skipping {species}: no TFs found in expression matrix")
        return []

    print(f"  {species}: {len(gene_names)} genes, {mat.n} samples, {len(tf_indices)} TFs")

    expr_matrix = np.array([mat.genes[g] for g in gene_names]).T
    expr_matrix = np.log2(expr_matrix + 1)

    t0 = time.time()
    results = Parallel(n_jobs=n_jobs, verbose=10)(
        delayed(_fit_one_target)(i, expr_matrix, tf_indices, gene_names, method, seed)
        for i in range(len(gene_names))
    )
    elapsed = time.time() - t0

    all_edges = []
    for edges in results:
        all_edges.extend(edges)

    print(f"  {method} completed in {elapsed:.1f}s, {len(all_edges)} raw edges")

    all_edges.sort(key=lambda x: -x[2])
    all_edges = all_edges[:top_edges]

    method_label = "GRNBoost2" if method == "grnboost2" else "GENIE3"
    return [
        {"tf": tf, "target": target, "importance": round(imp, 6), "method": method_label}
        for tf, target, imp in all_edges
    ]


def main():
    parser = argparse.ArgumentParser(description="Infer GRN edges from expression data")
    parser.add_argument("--species", help="Single species to process")
    parser.add_argument("--all", action="store_true", help="Process all species with expression data")
    parser.add_argument("--method", choices=["grnboost2", "genie3", "both"], default="both")
    parser.add_argument("--top-edges", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--jobs", type=int, default=-1, help="Parallel jobs (-1 = all cores)")
    args = parser.parse_args()

    if not args.species and not args.all:
        parser.error("Provide --species or --all")

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}. Run 'make db' first.", file=sys.stderr)
        sys.exit(1)

    species_list = species_with_expression() if args.all else [args.species]
    methods = ["grnboost2", "genie3"] if args.method == "both" else [args.method]

    for species in species_list:
        print(f"\nInferring edges for {species}...")
        all_edges = []
        for method in methods:
            print(f"  Running {method}...")
            edges = run_inference(species, method, args.top_edges, args.seed, args.jobs)
            all_edges.extend(edges)

        if not all_edges:
            continue

        out_path = DATA_DIR / f"inferred_grn_{species}.json.gz"
        with gzip.open(out_path, "wt") as f:
            json.dump(all_edges, f)
        print(f"  Wrote {len(all_edges)} edges to {out_path.name}")

    print("\nDone.")


if __name__ == "__main__":
    main()
