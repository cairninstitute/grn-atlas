#!/usr/bin/env python3
"""Large-scale Boltz-2 structural binding validation.

Tests n=50+50 for arabidopsis and human (100 edges × 2 species = 200 API calls).
Conservative rate limiting for NIM free tier.

Fixes from n=20 pilot:
  - Unique target genes (no duplicate targets)
  - Two species instead of one
  - Overall and per-species AUC via sklearn
  - Intermediate saves after each edge

Usage:
  nohup python backend/scripts/validate_boltz2_large_scale.py \
      --positives 50 --negatives 50 --rate-limit 2.0 \
      > /tmp/boltz2_large_validation.log 2>&1 &
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
OUT = Path(__file__).resolve().parents[1] / "data" / "boltz2_large_validation.json"

sys_path_added = False


def _ensure_imports():
    global sys_path_added
    if not sys_path_added:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        sys_path_added = True
    from predict_structural_binding import (
        ensure_tables, load_api_key, fetch_protein_sequence,
        fetch_promoter_dna, call_boltz2, classify_binding, SPECIES_CONFIG,
    )
    return (ensure_tables, load_api_key, fetch_protein_sequence,
            fetch_promoter_dna, call_boltz2, classify_binding, SPECIES_CONFIG)


def select_positive_controls(conn: sqlite3.Connection, species: str,
                             max_edges: int) -> list[dict]:
    rows = conn.execute("""
        SELECT i.source_id, gs.symbol, i.target_id, gt.symbol,
               i.sign, i.confidence
        FROM interactions i
        JOIN genes gs ON gs.id = i.source_id AND gs.species = ? AND gs.is_tf = 1
        JOIN genes gt ON gt.id = i.target_id AND gt.species = ?
        JOIN gene_locations gl1 ON gl1.gene_id = i.source_id
        JOIN gene_locations gl2 ON gl2.gene_id = i.target_id
        WHERE i.sign_evidence = 'measured'
          AND i.confidence >= 0.5
        ORDER BY RANDOM()
    """, (species, species)).fetchall()

    positives = []
    used_targets = set()
    for r in rows:
        if r[2] not in used_targets and len(positives) < max_edges:
            positives.append({
                "source_id": r[0], "source_symbol": r[1],
                "target_id": r[2], "target_symbol": r[3],
                "sign": r[4], "interaction_confidence": r[5],
                "species": species, "relation_type": r[4] or "activation",
                "control_type": "positive",
            })
            used_targets.add(r[2])
    return positives


def select_negative_controls(conn: sqlite3.Connection, species: str,
                             max_edges: int) -> list[dict]:
    tfs = conn.execute("""
        SELECT g.id, g.symbol FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id
        WHERE g.species = ? AND g.is_tf = 1
        ORDER BY RANDOM() LIMIT ?
    """, (species, max_edges * 3)).fetchall()

    non_targets = conn.execute("""
        SELECT g.id, g.symbol FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id
        WHERE g.species = ? AND g.is_tf = 0
        ORDER BY RANDOM() LIMIT ?
    """, (species, max_edges * 5)).fetchall()

    existing_pairs = set()
    for row in conn.execute("SELECT source_id, target_id FROM interactions"):
        existing_pairs.add((row[0], row[1]))

    negatives = []
    used_targets = set()
    random.shuffle(tfs)
    random.shuffle(non_targets)
    for tf_id, tf_sym in tfs:
        for tgt_id, tgt_sym in non_targets:
            if ((tf_id, tgt_id) not in existing_pairs
                    and tgt_id not in used_targets
                    and tf_id != tgt_id):
                negatives.append({
                    "source_id": tf_id, "source_symbol": tf_sym,
                    "target_id": tgt_id, "target_symbol": tgt_sym,
                    "species": species, "relation_type": "activation",
                    "control_type": "negative",
                })
                used_targets.add(tgt_id)
                break
        if len(negatives) >= max_edges:
            break
    return negatives


def compute_auc(pos_scores: list[float], neg_scores: list[float]) -> float | None:
    if len(pos_scores) < 2 or len(neg_scores) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score
        labels = [1] * len(pos_scores) + [0] * len(neg_scores)
        scores = pos_scores + neg_scores
        return round(roc_auc_score(labels, scores), 4)
    except Exception:
        return None


def stats(scores: list[float]) -> dict:
    if not scores:
        return {"n": 0}
    s = sorted(scores)
    return {
        "n": len(s), "min": round(s[0], 4), "max": round(s[-1], 4),
        "mean": round(np.mean(s), 4), "median": round(np.median(s), 4),
        "std": round(np.std(s), 4),
        "q25": round(np.percentile(s, 25), 4),
        "q75": round(np.percentile(s, 75), 4),
    }


def run_species(species: str, conn: sqlite3.Connection, api_key: str,
                max_pos: int, max_neg: int, dna_window: int,
                rate_limit: float) -> dict:
    (ensure_tables, _, fetch_protein_sequence,
     fetch_promoter_dna, call_boltz2, classify_binding, _) = _ensure_imports()

    pos = select_positive_controls(conn, species, max_pos)
    neg = select_negative_controls(conn, species, max_neg)
    print(f"\n{'='*60}", flush=True)
    print(f"Species: {species}", flush=True)
    print(f"Positive controls: {len(pos)} (unique targets: {len(set(p['target_id'] for p in pos))})", flush=True)
    print(f"Negative controls: {len(neg)} (unique targets: {len(set(n['target_id'] for n in neg))})", flush=True)

    all_edges = pos + neg
    start_time = time.time()

    for i, edge in enumerate(all_edges):
        label = edge["control_type"]
        src = edge.get("source_symbol", edge["source_id"])
        tgt = edge.get("target_symbol", edge["target_id"])
        print(f"[{species} {i+1}/{len(all_edges)}] ({label}) {src} -> {tgt}...", end=" ", flush=True)

        try:
            protein_seq = fetch_protein_sequence(
                edge["source_id"], edge.get("source_symbol", ""),
                species, conn)
            if not protein_seq:
                edge["confidence_score"] = None
                edge["binding_class"] = "no_sequence"
                edge["error"] = "protein not found"
                print("no_protein", flush=True)
                continue

            dna_seq = fetch_promoter_dna(edge["target_id"], species, conn, dna_window)
            if not dna_seq:
                edge["confidence_score"] = None
                edge["binding_class"] = "no_sequence"
                edge["error"] = "DNA not found"
                print("no_dna", flush=True)
                continue

            result = call_boltz2(protein_seq, dna_seq, api_key)
            if not result or "error" in result:
                edge["confidence_score"] = None
                edge["binding_class"] = "error"
                edge["error"] = str(result.get("error", "unknown"))[:200] if result else "no response"
                print(f"api_error", flush=True)
                continue

            scores = result.get("confidence_scores", [])
            confidence = scores[0] if scores else None
            edge["confidence_score"] = confidence
            edge["binding_class"] = classify_binding(confidence)
            edge["protein_length"] = len(protein_seq)
            edge["dna_length"] = len(dna_seq)
            score_str = f"{confidence:.4f}" if confidence is not None else "n/a"
            print(f"{edge['binding_class']} ({score_str})", flush=True)

        except Exception as exc:
            edge["confidence_score"] = None
            edge["binding_class"] = "error"
            edge["error"] = str(exc)[:200]
            print(f"error: {exc}", flush=True)

        if i < len(all_edges) - 1:
            time.sleep(rate_limit)

    elapsed = time.time() - start_time

    pos_scores = [e["confidence_score"] for e in all_edges
                  if e["control_type"] == "positive" and e.get("confidence_score") is not None]
    neg_scores = [e["confidence_score"] for e in all_edges
                  if e["control_type"] == "negative" and e.get("confidence_score") is not None]

    auc = compute_auc(pos_scores, neg_scores)
    sep = round(np.mean(pos_scores) - np.mean(neg_scores), 4) if pos_scores and neg_scores else None

    return {
        "species": species,
        "dna_window": dna_window,
        "n_scored": {"positives": len(pos_scores), "negatives": len(neg_scores)},
        "unique_targets": {
            "positives": len(set(e["target_id"] for e in all_edges
                                 if e["control_type"] == "positive" and e.get("confidence_score") is not None)),
            "negatives": len(set(e["target_id"] for e in all_edges
                                 if e["control_type"] == "negative" and e.get("confidence_score") is not None)),
        },
        "positive_controls": stats(pos_scores),
        "negative_controls": stats(neg_scores),
        "mean_separation": sep,
        "auc": auc,
        "runtime_minutes": round(elapsed / 60, 1),
        "all_results": all_edges,
    }


def main():
    parser = argparse.ArgumentParser(description="Large-scale Boltz-2 binding validation")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", nargs="+", default=["arabidopsis", "human"])
    parser.add_argument("--positives", type=int, default=50)
    parser.add_argument("--negatives", type=int, default=50)
    parser.add_argument("--dna-window", type=int, default=200)
    parser.add_argument("--rate-limit", type=float, default=2.0,
                        help="Seconds between API calls (default 2.0 for NIM free tier)")
    args = parser.parse_args()

    (_, load_api_key, _, _, _, _, _) = _ensure_imports()

    api_key = load_api_key()
    if not api_key:
        print("ERROR: NVIDIA_NIM_API_KEY not set. Source ~/.secrets.env first.")
        return 1

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")

    species_results = {}
    start_total = time.time()

    for species in args.species:
        result = run_species(species, conn, api_key, args.positives,
                             args.negatives, args.dna_window, args.rate_limit)
        species_results[species] = result

        partial_report = {
            "validation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": "Boltz-2 (NVIDIA NIM)",
            "status": "in_progress",
            "species_completed": list(species_results.keys()),
            "species_remaining": [s for s in args.species if s not in species_results],
            "results": {k: {kk: vv for kk, vv in v.items() if kk != "all_results"}
                        for k, v in species_results.items()},
            "all_results": species_results,
        }
        OUT.write_text(json.dumps(partial_report, indent=2, default=str))
        print(f"\nIntermediate results saved to {OUT}", flush=True)

    total_elapsed = time.time() - start_total

    report = {
        "validation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "Boltz-2 (NVIDIA NIM)",
        "dna_window": args.dna_window,
        "status": "complete",
        "total_runtime_minutes": round(total_elapsed / 60, 1),
        "species_results": {k: {kk: vv for kk, vv in v.items() if kk != "all_results"}
                            for k, v in species_results.items()},
        "all_results": species_results,
    }

    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n{'='*60}", flush=True)
    print(f"COMPLETE. Total runtime: {total_elapsed/60:.1f} minutes", flush=True)
    for sp, r in species_results.items():
        print(f"  {sp}: AUC={r['auc']}  separation={r['mean_separation']}  "
              f"n={r['n_scored']['positives']}+{r['n_scored']['negatives']}", flush=True)
    print(f"Saved to {OUT}", flush=True)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
