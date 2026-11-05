#!/usr/bin/env python3
"""Perturbation-supervised directed GRN inference.

Enhances GENIE3/GRNBoost2 with perturbation observations from KnockTF and
ConnecTF to produce directed, signed, confidence-calibrated regulatory edges.

The approach:
  1. Run standard GENIE3 per target gene → importance scores (TF→target)
  2. Build perturbation ground truth from knockdown/induction DEGs
  3. Calibrate importance thresholds against perturbation-validated edges
  4. Assign signs (activation/repression) from perturbation fold changes
  5. Output directed edges with calibrated precision and perturbation support

This produces a higher-quality directed network than raw GENIE3/GRNBoost2
by leveraging the 223K+ perturbation observations now in the atlas.

Usage:
    python backend/scripts/infer_directed_grn.py --species arabidopsis
    python backend/scripts/infer_directed_grn.py --all
    python backend/scripts/infer_directed_grn.py --species arabidopsis --dry-run
"""
from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import precision_recall_curve, auc

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

sys.path.insert(0, str(REPO))
from expression import get_matrix, species_with_expression

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

DATASET_ORIENTATION = {
    "connectf_target": +1,
    "knocktf": -1,
}

MIN_ABS_LOG2FC = 1.0
MIN_OBSERVATIONS = 2


def get_tf_list(conn: sqlite3.Connection, species: str) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT id FROM genes WHERE species = ? AND is_tf = 1", (species,)
    ).fetchall()]


def build_perturbation_ground_truth(
    conn: sqlite3.Connection, species: str
) -> tuple[dict[tuple[str, str], dict], set[str]]:
    """Build ground-truth directed edges from perturbation observations.

    Returns:
        edges: dict mapping (tf_id, target_id) → {sign, mean_fc, n_obs, confidence}
        perturbed_tfs: set of TF IDs that have perturbation data
    """
    labels = tuple(DATASET_ORIENTATION)
    placeholders = ",".join("?" * len(labels))
    rows = conn.execute(
        f"SELECT perturbed_gene, affected_gene, observed_log2fc, dataset_label "
        f"FROM perturbation_observations "
        f"WHERE dataset_label IN ({placeholders}) AND observed_significant = 1 "
        f"AND species = ?",
        (*labels, species),
    ).fetchall()

    raw: dict[tuple[str, str], list[float]] = defaultdict(list)
    for tf, target, fc, label in rows:
        if fc is None or tf == target:
            continue
        orientation = DATASET_ORIENTATION[label]
        raw[(tf, target)].append(fc * orientation)

    edges = {}
    perturbed_tfs = set()
    for (tf, target), scores in raw.items():
        if len(scores) < MIN_OBSERVATIONS:
            continue
        mean_score = statistics.mean(scores)
        if abs(mean_score) < MIN_ABS_LOG2FC:
            continue
        sign = "activation" if mean_score > 0 else "repression"
        consistency = sum(1 for s in scores if (s > 0) == (mean_score > 0)) / len(scores)
        edges[(tf, target)] = {
            "sign": sign,
            "mean_fc": round(mean_score, 4),
            "n_obs": len(scores),
            "consistency": round(consistency, 4),
            "confidence": round(min(0.95, 0.5 + 0.1 * min(len(scores), 5) * consistency), 4),
        }
        perturbed_tfs.add(tf)

    return edges, perturbed_tfs


def _fit_one_target(target_idx, expr_matrix, tf_indices, gene_names, seed):
    predictor_indices = [i for i in tf_indices if i != target_idx]
    if not predictor_indices:
        return []

    X = expr_matrix[:, predictor_indices]
    y = expr_matrix[:, target_idx]

    if np.std(y) == 0:
        return []

    rng = np.random.RandomState(seed + target_idx)

    gb_model = GradientBoostingRegressor(random_state=rng, **GRNBOOST2_PARAMS)
    gb_model.fit(X, y)
    gb_imp = gb_model.feature_importances_

    rf_model = RandomForestRegressor(random_state=rng, n_jobs=1, **GENIE3_PARAMS)
    rf_model.fit(X, y)
    rf_imp = rf_model.feature_importances_

    target_name = gene_names[target_idx]
    edges = []
    for i in range(len(predictor_indices)):
        combined = (gb_imp[i] + rf_imp[i]) / 2.0
        if combined > 1e-6:
            edges.append((
                gene_names[predictor_indices[i]],
                target_name,
                float(combined),
                float(gb_imp[i]),
                float(rf_imp[i]),
            ))
    return edges


def calibrate_threshold(
    inferred: list[tuple], ground_truth: dict[tuple[str, str], dict]
) -> tuple[float, dict]:
    """Find optimal importance threshold using perturbation ground truth.

    Uses a 50/50 TF-stratified split: threshold is chosen on the train half
    and AUPRC is reported on the held-out test half to avoid optimistic bias.
    """
    gt_set = set(ground_truth.keys())
    if not gt_set or not inferred:
        return 0.0, {"auprc": 0.0, "n_gt": 0, "n_inferred": 0}

    gt_tfs = sorted({tf for tf, _ in gt_set})
    rng = np.random.RandomState(42)
    rng.shuffle(gt_tfs)
    mid = max(1, len(gt_tfs) // 2)
    train_tfs = set(gt_tfs[:mid])
    test_tfs = set(gt_tfs[mid:])

    def _score_split(tf_subset):
        labs, scs = [], []
        subset_gt = {(t, tgt) for t, tgt in gt_set if t in tf_subset}
        for tf, target, importance, _, _ in inferred:
            if tf not in tf_subset:
                continue
            labs.append(1 if (tf, target) in subset_gt else 0)
            scs.append(importance)
        return np.array(labs), np.array(scs)

    train_labels, train_scores = _score_split(train_tfs)
    test_labels, test_scores = _score_split(test_tfs)

    if train_labels.sum() == 0 or test_labels.sum() == 0:
        return 0.0, {"auprc": 0.0, "n_gt": len(gt_set), "n_inferred": len(inferred),
                      "note": "too few ground-truth edges for train/test split"}

    train_prec, train_rec, train_thresh = precision_recall_curve(train_labels, train_scores)
    train_f1 = 2 * train_prec * train_rec / (train_prec + train_rec + 1e-10)
    best_idx = np.argmax(train_f1[:-1])
    optimal_threshold = float(train_thresh[best_idx])

    test_prec, test_rec, _ = precision_recall_curve(test_labels, test_scores)
    test_auprc = auc(test_rec, test_prec)

    above = test_scores >= optimal_threshold
    if above.sum() > 0:
        held_out_prec = float(test_labels[above].sum() / above.sum())
        held_out_rec = float(test_labels[above].sum() / max(1, test_labels.sum()))
    else:
        held_out_prec, held_out_rec = 0.0, 0.0

    return optimal_threshold, {
        "auprc_held_out": round(float(test_auprc), 4),
        "optimal_threshold": round(optimal_threshold, 6),
        "precision_held_out": round(held_out_prec, 4),
        "recall_held_out": round(held_out_rec, 4),
        "n_gt": int(train_labels.sum() + test_labels.sum()),
        "n_gt_train": int(train_labels.sum()),
        "n_gt_test": int(test_labels.sum()),
        "n_inferred": len(inferred),
    }


def get_existing_signs(conn: sqlite3.Connection, species: str) -> dict[tuple[str, str], str]:
    """Get signed edges from the interactions table for sign transfer."""
    prefix_map = {
        "arabidopsis": "AT",
        "human": "ENSG",
        "mouse": "ENSMUSG",
        "tomato": "Solyc",
        "petunia": "Peaxi",
        "rice": "LOC_Os",
    }
    prefix = prefix_map.get(species, "")
    if not prefix:
        return {}
    rows = conn.execute(
        "SELECT source_id, target_id, sign FROM interactions "
        "WHERE sign IS NOT NULL AND source_id LIKE ?",
        (prefix + "%",),
    ).fetchall()
    return {(r[0], r[1]): r[2] for r in rows}


def run_directed_inference(
    species: str,
    conn: sqlite3.Connection,
    top_edges: int = 200_000,
    seed: int = 42,
    n_jobs: int = -1,
) -> dict:
    """Run perturbation-supervised directed GRN inference."""
    mat = get_matrix(species)
    if mat is None:
        return {"species": species, "error": "no expression matrix"}

    tf_ids = get_tf_list(conn, species)
    gene_names = list(mat.genes.keys())
    tf_set = set(tf_ids)
    tf_indices = [i for i, g in enumerate(gene_names) if g in tf_set]

    if not tf_indices:
        return {"species": species, "error": "no TFs in expression matrix"}

    print(f"  {species}: {len(gene_names)} genes, {mat.n} samples, {len(tf_indices)} TFs")

    print(f"  Building perturbation ground truth...", flush=True)
    ground_truth, perturbed_tfs = build_perturbation_ground_truth(conn, species)

    print(f"  Loading existing signed interactions...", flush=True)
    existing_signs = get_existing_signs(conn, species)
    print(f"  Existing signed edges: {len(existing_signs):,}")
    print(f"  Ground truth: {len(ground_truth)} directed edges from "
          f"{len(perturbed_tfs)} perturbed TFs")

    expr_matrix = np.array([mat.genes[g] for g in gene_names]).T
    expr_matrix = np.log2(expr_matrix + 1)

    print(f"  Running ensemble inference (GRNBoost2 + GENIE3)...", flush=True)
    t0 = time.time()
    results = Parallel(n_jobs=n_jobs, verbose=5)(
        delayed(_fit_one_target)(i, expr_matrix, tf_indices, gene_names, seed)
        for i in range(len(gene_names))
    )
    elapsed = time.time() - t0

    all_edges = []
    for edges in results:
        all_edges.extend(edges)
    all_edges.sort(key=lambda x: -x[2])
    print(f"  Inference completed in {elapsed:.1f}s, {len(all_edges)} raw edges")

    print(f"  Calibrating against perturbation ground truth...", flush=True)
    threshold, calibration = calibrate_threshold(all_edges, ground_truth)
    print(f"  Calibration: AUPRC={calibration['auprc']}, "
          f"threshold={calibration.get('optimal_threshold', 'N/A')}")

    directed_edges = []
    n_perturbation_supported = 0
    n_perturbation_signed = 0
    n_existing_signed = 0
    n_expression_only = 0
    sign_counts = defaultdict(int)

    for tf, target, importance, gb_imp, rf_imp in all_edges:
        if importance < threshold * 0.5:
            continue

        gt = ground_truth.get((tf, target))
        existing_sign = existing_signs.get((tf, target))

        if gt:
            sign = gt["sign"]
            sign_evidence = "perturbation"
            confidence = round(min(0.95, importance * 2 + gt["confidence"] * 0.3), 4)
            n_perturbation_supported += 1
            n_perturbation_signed += 1
        elif existing_sign:
            sign = existing_sign
            sign_evidence = "curated_transfer"
            confidence = round(min(0.90, importance * 1.8), 4)
            n_existing_signed += 1
        elif tf in perturbed_tfs:
            sign = None
            sign_evidence = "absent"
            confidence = round(importance * 1.5, 4)
            n_expression_only += 1
        else:
            sign = None
            sign_evidence = "no_perturbation_data"
            confidence = round(importance, 4)
            n_expression_only += 1

        confidence = min(0.95, max(0.01, confidence))

        if sign:
            sign_counts[sign] += 1

        directed_edges.append({
            "source_id": tf,
            "target_id": target,
            "importance": round(importance, 6),
            "grnboost2_importance": round(gb_imp, 6),
            "genie3_importance": round(rf_imp, 6),
            "confidence": confidence,
            "sign": sign,
            "sign_evidence": sign_evidence,
            "perturbation_support": gt is not None,
            "perturbation_n_obs": gt["n_obs"] if gt else 0,
            "perturbation_consistency": gt["consistency"] if gt else None,
            "perturbation_mean_fc": gt["mean_fc"] if gt else None,
        })

        if len(directed_edges) >= top_edges:
            break

    return {
        "species": species,
        "n_genes": len(gene_names),
        "n_samples": mat.n,
        "n_tfs": len(tf_indices),
        "n_raw_edges": len(all_edges),
        "n_directed_edges": len(directed_edges),
        "n_perturbation_supported": n_perturbation_supported,
        "n_perturbation_signed": n_perturbation_signed,
        "n_existing_signed": n_existing_signed,
        "n_expression_only": n_expression_only,
        "sign_counts": dict(sign_counts),
        "calibration": calibration,
        "threshold": round(threshold, 6),
        "inference_time_s": round(elapsed, 1),
        "edges": directed_edges,
    }


def store_directed_edges(
    conn: sqlite3.Connection, species: str, result: dict, dry_run: bool = False
) -> int:
    """Store directed inferred edges in the database."""
    edges = result.get("edges", [])
    if not edges or dry_run:
        return 0

    conn.execute("""
        CREATE TABLE IF NOT EXISTS directed_inferred_edges (
            source_id       TEXT NOT NULL,
            target_id       TEXT NOT NULL,
            species         TEXT NOT NULL,
            importance      REAL NOT NULL,
            grnboost2_imp   REAL,
            genie3_imp      REAL,
            confidence      REAL NOT NULL,
            sign            TEXT,
            sign_evidence   TEXT NOT NULL DEFAULT 'no_perturbation_data',
            perturbation_support INTEGER NOT NULL DEFAULT 0,
            perturbation_n_obs   INTEGER NOT NULL DEFAULT 0,
            perturbation_consistency REAL,
            perturbation_mean_fc     REAL,
            PRIMARY KEY (source_id, target_id, species)
        )
    """)

    conn.execute("DELETE FROM directed_inferred_edges WHERE species = ?", (species,))

    conn.executemany(
        "INSERT INTO directed_inferred_edges "
        "(source_id, target_id, species, importance, grnboost2_imp, genie3_imp, "
        " confidence, sign, sign_evidence, perturbation_support, "
        " perturbation_n_obs, perturbation_consistency, perturbation_mean_fc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(e["source_id"], e["target_id"], species,
          e["importance"], e["grnboost2_importance"], e["genie3_importance"],
          e["confidence"], e["sign"], e["sign_evidence"],
          1 if e["perturbation_support"] else 0,
          e["perturbation_n_obs"], e["perturbation_consistency"],
          e["perturbation_mean_fc"])
         for e in edges],
    )
    conn.commit()
    return len(edges)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--species", help="Single species to process")
    parser.add_argument("--all", action="store_true", help="All species with expression data")
    parser.add_argument("--top-edges", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--jobs", type=int, default=-1)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.species and not args.all:
        parser.error("Provide --species or --all")

    species_list = species_with_expression() if args.all else [args.species]

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    summary = {}
    for species in species_list:
        print(f"\n{'='*60}")
        print(f"Directed inference for {species}")
        print(f"{'='*60}")

        result = run_directed_inference(
            species, conn, top_edges=args.top_edges, seed=args.seed, n_jobs=args.jobs)

        if "error" in result:
            print(f"  Skipped: {result['error']}")
            summary[species] = {"error": result["error"]}
            continue

        n_stored = store_directed_edges(conn, species, result, dry_run=args.dry_run)
        prefix = "[DRY RUN] " if args.dry_run else ""
        print(f"\n{prefix}Results for {species}:")
        print(f"  Directed edges: {result['n_directed_edges']:,}")
        print(f"  Perturbation-supported: {result['n_perturbation_supported']:,}")
        print(f"  Perturbation-signed: {result['n_perturbation_signed']:,}")
        print(f"  Curated-signed: {result.get('n_existing_signed', 0):,}")
        print(f"  Expression-only: {result['n_expression_only']:,}")
        print(f"  Signs: {result['sign_counts']}")
        print(f"  Calibration AUPRC: {result['calibration']['auprc']}")
        if not args.dry_run:
            print(f"  Stored: {n_stored:,} edges")

        out = {k: v for k, v in result.items() if k != "edges"}
        summary[species] = out

        out_path = DATA_DIR / f"directed_grn_{species}.json.gz"
        with gzip.open(out_path, "wt") as f:
            json.dump(result["edges"], f)
        print(f"  Wrote {len(result['edges']):,} edges to {out_path.name}")

    conn.close()

    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
