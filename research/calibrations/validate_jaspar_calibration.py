#!/usr/bin/env python3
"""JASPAR motif scanning calibration.

Tests whether JASPAR motif hits in promoters discriminate known TF-target
interactions from random TF-gene pairs. Purely database-driven — no API calls,
no GPU, runs in seconds.

For each TF with a JASPAR motif:
  - Positive controls: measured interactions (TF -> target) where the motif
    hits the target's promoter region
  - Negative controls: random genes (not known targets of this TF) where
    the motif may or may not hit

Scores: best motif hit p-value in the target's promoter.
Metrics: AUC (can motif presence distinguish real targets from random?),
         motif hit rate in positives vs negatives.

Species: arabidopsis (TAIR10), tomato (SL4.0), petunia (Peaxi162v1.6.2)
— these are the species with both JASPAR motifs and motif_hits in the database.

Usage:
  nohup python backend/scripts/validate_jaspar_calibration.py \
      --max-per-tf 50 \
      > /tmp/jaspar_calibration.log 2>&1 &
"""

from __future__ import annotations

import json
import random
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
OUT = Path(__file__).resolve().parents[1] / "data" / "jaspar_calibration.json"

ASSEMBLY_MAP = {
    "arabidopsis": "TAIR10",
    "tomato": "SL4.0",
    "petunia": "Peaxi162v1.6.2",
}


def compute_auc(pos_scores: list[float], neg_scores: list[float]) -> float | None:
    if len(pos_scores) < 5 or len(neg_scores) < 5:
        return None
    try:
        from sklearn.metrics import roc_auc_score
        labels = [1] * len(pos_scores) + [0] * len(neg_scores)
        scores = pos_scores + neg_scores
        return round(roc_auc_score(labels, scores), 4)
    except Exception:
        return None


def get_best_motif_score(conn: sqlite3.Connection, motif_id: str,
                         gene_id: str, assembly: str) -> dict:
    """Get best motif hit for a TF's motif in a gene's promoter region."""
    rows = conn.execute("""
        SELECT score, p_value, tier, site_confidence, window_type
        FROM motif_hits
        WHERE motif_id = ? AND ext_gene_id = ? AND assembly = ?
        ORDER BY p_value ASC
        LIMIT 1
    """, (motif_id, gene_id, assembly)).fetchall()

    if rows:
        r = rows[0]
        return {
            "has_hit": True,
            "best_score": r[0],
            "best_pvalue": r[1],
            "tier": r[2],
            "site_confidence": r[3],
            "window_type": r[4],
            "neg_log_pvalue": -np.log10(r[1]) if r[1] and r[1] > 0 else 0,
        }
    return {
        "has_hit": False,
        "best_score": 0,
        "best_pvalue": 1.0,
        "tier": None,
        "site_confidence": None,
        "window_type": None,
        "neg_log_pvalue": 0,
    }


def run_species(conn: sqlite3.Connection, species: str, assembly: str,
                max_per_tf: int) -> dict:
    print(f"\n{'='*60}", flush=True)
    print(f"Species: {species} (assembly: {assembly})", flush=True)

    tf_motifs = conn.execute("""
        SELECT m.motif_id, m.tf_gene_id, m.tf_symbol
        FROM motifs m
        JOIN genes g ON g.id = m.tf_gene_id
        WHERE g.species = ?
    """, (species,)).fetchall()
    print(f"TFs with JASPAR motifs: {len(tf_motifs)}", flush=True)

    measured_interactions = conn.execute("""
        SELECT i.source_id, i.target_id
        FROM interactions i
        JOIN genes gs ON gs.id = i.source_id AND gs.species = ?
        WHERE i.sign_evidence = 'measured'
    """, (species,)).fetchall()

    known_targets = defaultdict(set)
    for src, tgt in measured_interactions:
        known_targets[src].add(tgt)
    print(f"TFs with measured interactions: {len(known_targets)}", flush=True)

    all_known_pairs = set((src, tgt) for src, tgt in measured_interactions)

    all_genes = [r[0] for r in conn.execute(
        "SELECT id FROM genes WHERE species = ?", (species,)).fetchall()]
    print(f"Total genes: {len(all_genes)}", flush=True)

    genes_with_hits = set(r[0] for r in conn.execute(
        "SELECT DISTINCT ext_gene_id FROM motif_hits WHERE assembly = ?",
        (assembly,)).fetchall())
    print(f"Genes with any motif hit: {len(genes_with_hits)}", flush=True)

    per_tf_results = {}
    all_pos_scores = []
    all_neg_scores = []
    all_pos_hits = 0
    all_pos_total = 0
    all_neg_hits = 0
    all_neg_total = 0
    tfs_tested = 0

    for motif_id, tf_gene_id, tf_symbol in tf_motifs:
        targets = list(known_targets.get(tf_gene_id, set()))
        if len(targets) < 3:
            continue

        random.shuffle(targets)
        pos_targets = targets[:max_per_tf]

        non_targets = [g for g in all_genes
                       if g != tf_gene_id and (tf_gene_id, g) not in all_known_pairs]
        random.shuffle(non_targets)
        neg_targets = non_targets[:len(pos_targets)]

        pos_results = []
        for tgt in pos_targets:
            hit = get_best_motif_score(conn, motif_id, tgt, assembly)
            hit["gene_id"] = tgt
            hit["control_type"] = "positive"
            pos_results.append(hit)

        neg_results = []
        for tgt in neg_targets:
            hit = get_best_motif_score(conn, motif_id, tgt, assembly)
            hit["gene_id"] = tgt
            hit["control_type"] = "negative"
            neg_results.append(hit)

        pos_hit_rate = sum(1 for r in pos_results if r["has_hit"]) / len(pos_results) if pos_results else 0
        neg_hit_rate = sum(1 for r in neg_results if r["has_hit"]) / len(neg_results) if neg_results else 0

        pos_scores = [r["neg_log_pvalue"] for r in pos_results]
        neg_scores = [r["neg_log_pvalue"] for r in neg_results]

        auc = compute_auc(pos_scores, neg_scores)

        per_tf_results[tf_symbol or motif_id] = {
            "motif_id": motif_id,
            "tf_gene_id": tf_gene_id,
            "n_positive": len(pos_results),
            "n_negative": len(neg_results),
            "pos_hit_rate": round(pos_hit_rate, 3),
            "neg_hit_rate": round(neg_hit_rate, 3),
            "hit_rate_ratio": round(pos_hit_rate / neg_hit_rate, 3) if neg_hit_rate > 0 else None,
            "mean_pos_score": round(np.mean(pos_scores), 4) if pos_scores else None,
            "mean_neg_score": round(np.mean(neg_scores), 4) if neg_scores else None,
            "auc": auc,
        }

        all_pos_scores.extend(pos_scores)
        all_neg_scores.extend(neg_scores)
        all_pos_hits += sum(1 for r in pos_results if r["has_hit"])
        all_pos_total += len(pos_results)
        all_neg_hits += sum(1 for r in neg_results if r["has_hit"])
        all_neg_total += len(neg_results)
        tfs_tested += 1

    overall_auc = compute_auc(all_pos_scores, all_neg_scores)

    tf_aucs = [r["auc"] for r in per_tf_results.values() if r["auc"] is not None]
    tf_hit_ratios = [r["hit_rate_ratio"] for r in per_tf_results.values()
                     if r["hit_rate_ratio"] is not None]

    result = {
        "species": species,
        "assembly": assembly,
        "tfs_with_motifs": len(tf_motifs),
        "tfs_with_measured_targets": len([tf for tf in tf_motifs if tf[1] in known_targets]),
        "tfs_tested": tfs_tested,
        "total_positive_pairs": all_pos_total,
        "total_negative_pairs": all_neg_total,
        "overall_pos_hit_rate": round(all_pos_hits / all_pos_total, 3) if all_pos_total else None,
        "overall_neg_hit_rate": round(all_neg_hits / all_neg_total, 3) if all_neg_total else None,
        "overall_auc": overall_auc,
        "mean_per_tf_auc": round(np.mean(tf_aucs), 4) if tf_aucs else None,
        "median_per_tf_auc": round(np.median(tf_aucs), 4) if tf_aucs else None,
        "mean_hit_rate_ratio": round(np.mean(tf_hit_ratios), 3) if tf_hit_ratios else None,
        "per_tf_results": per_tf_results,
    }

    print(f"\nResults for {species}:", flush=True)
    print(f"  TFs tested: {tfs_tested}", flush=True)
    print(f"  Total pairs: {all_pos_total} positive, {all_neg_total} negative", flush=True)
    print(f"  Hit rates: pos={result['overall_pos_hit_rate']}, neg={result['overall_neg_hit_rate']}", flush=True)
    print(f"  Overall AUC (pooled): {overall_auc}", flush=True)
    print(f"  Mean per-TF AUC: {result['mean_per_tf_auc']}", flush=True)
    print(f"  Median per-TF AUC: {result['median_per_tf_auc']}", flush=True)

    if per_tf_results:
        top = sorted(per_tf_results.items(),
                     key=lambda x: x[1].get("auc") or 0, reverse=True)[:10]
        print(f"\n  Top 10 TFs by AUC:", flush=True)
        for tf, r in top:
            print(f"    {tf:20s}: AUC={r['auc']}  hit_ratio={r['hit_rate_ratio']}  "
                  f"n={r['n_positive']}+{r['n_negative']}", flush=True)

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="JASPAR motif scanning calibration")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", nargs="+", default=list(ASSEMBLY_MAP.keys()))
    parser.add_argument("--max-per-tf", type=int, default=50,
                        help="Max positive/negative targets per TF (default 50)")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")

    start = time.time()
    species_results = {}

    for species in args.species:
        assembly = ASSEMBLY_MAP.get(species)
        if not assembly:
            print(f"Skipping {species}: no assembly mapping", flush=True)
            continue

        hit_count = conn.execute(
            "SELECT count(*) FROM motif_hits WHERE assembly = ?",
            (assembly,)).fetchone()[0]
        if hit_count == 0:
            print(f"Skipping {species}: no motif hits for assembly {assembly}", flush=True)
            continue

        result = run_species(conn, species, assembly, args.max_per_tf)
        species_results[species] = result

        partial = {
            "validation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": "JASPAR 2024 motif scanning",
            "status": "in_progress",
            "species_completed": list(species_results.keys()),
            "results": species_results,
        }
        OUT.write_text(json.dumps(partial, indent=2, default=str))

    elapsed = time.time() - start

    report = {
        "validation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "JASPAR 2024 motif scanning",
        "status": "complete",
        "total_runtime_seconds": round(elapsed, 1),
        "species_results": species_results,
    }

    OUT.write_text(json.dumps(report, indent=2, default=str))

    print(f"\n{'='*60}", flush=True)
    print(f"COMPLETE in {elapsed:.1f} seconds", flush=True)
    for sp, r in species_results.items():
        print(f"  {sp}: overall_AUC={r['overall_auc']}  "
              f"mean_per_TF_AUC={r['mean_per_tf_auc']}  "
              f"hit_ratio pos/neg={r['overall_pos_hit_rate']}/{r['overall_neg_hit_rate']}  "
              f"TFs={r['tfs_tested']}", flush=True)
    print(f"Saved to {OUT}", flush=True)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
