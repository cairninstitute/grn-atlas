#!/usr/bin/env python3
"""Calibrate Boltz-2 structural binding predictions against known bindings.

Runs the same prediction pipeline on two sets of edges:
  - Positive controls: measured TF-DNA binding (sign_evidence='measured', high confidence)
  - Negative controls: random TF-gene pairs with no known regulatory relationship

Compares the score distributions to determine whether Boltz-2 confidence
distinguishes real bindings from random pairs, and whether the current
classification thresholds (0.7/0.4) need adjustment.

Usage:
  python backend/scripts/calibrate_structural_binding.py \
      --species arabidopsis --positives 30 --negatives 30
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"

from predict_structural_binding import (
    ensure_tables, load_api_key, fetch_protein_sequence,
    fetch_promoter_dna, call_boltz2, classify_binding, SPECIES_CONFIG,
)


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
          AND i.confidence >= 0.7
        ORDER BY i.confidence DESC, RANDOM()
        LIMIT ?
    """, (species, species, max_edges)).fetchall()
    return [{
        "source_id": r[0], "source_symbol": r[1],
        "target_id": r[2], "target_symbol": r[3],
        "sign": r[4], "interaction_confidence": r[5],
        "species": species, "relation_type": r[4] or "activation",
        "control_type": "positive",
    } for r in rows]


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
    """, (species, max_edges * 3)).fetchall()

    existing_pairs = set()
    for row in conn.execute(
        "SELECT source_id, target_id FROM interactions"
    ):
        existing_pairs.add((row[0], row[1]))

    negatives = []
    random.shuffle(tfs)
    random.shuffle(non_targets)
    for tf_id, tf_sym in tfs:
        for tgt_id, tgt_sym in non_targets:
            if (tf_id, tgt_id) not in existing_pairs and tf_id != tgt_id:
                negatives.append({
                    "source_id": tf_id, "source_symbol": tf_sym,
                    "target_id": tgt_id, "target_symbol": tgt_sym,
                    "species": species, "relation_type": "activation",
                    "control_type": "negative",
                })
                if len(negatives) >= max_edges:
                    break
        if len(negatives) >= max_edges:
            break
    return negatives


def run_prediction(edge: dict, conn: sqlite3.Connection, api_key: str,
                   dna_window: int) -> dict:
    species = edge["species"]
    source_id = edge["source_id"]
    symbol = edge.get("source_symbol", source_id)

    protein_seq = fetch_protein_sequence(source_id, symbol, species, conn)
    if not protein_seq:
        edge["confidence_score"] = None
        edge["binding_class"] = "no_sequence"
        edge["error"] = "protein not found"
        return edge

    dna_seq = fetch_promoter_dna(edge["target_id"], species, conn, dna_window)
    if not dna_seq:
        edge["confidence_score"] = None
        edge["binding_class"] = "no_sequence"
        edge["error"] = "DNA not found"
        return edge

    result = call_boltz2(protein_seq, dna_seq, api_key)
    if not result or "error" in result:
        edge["confidence_score"] = None
        edge["binding_class"] = "error"
        edge["error"] = str(result.get("error", "unknown"))[:200] if result else "no response"
        return edge

    scores = result.get("confidence_scores", [])
    confidence = scores[0] if scores else None
    edge["confidence_score"] = confidence
    edge["binding_class"] = classify_binding(confidence)
    edge["protein_length"] = len(protein_seq)
    edge["dna_length"] = len(dna_seq)
    return edge


def main():
    parser = argparse.ArgumentParser(description="Calibrate Boltz-2 structural binding")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="arabidopsis")
    parser.add_argument("--positives", type=int, default=30)
    parser.add_argument("--negatives", type=int, default=30)
    parser.add_argument("--dna-window", type=int, default=200)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    args = parser.parse_args()

    api_key = load_api_key()
    if not api_key:
        print("ERROR: NVIDIA_NIM_API_KEY not set.")
        return 1

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_tables(conn)

    pos = select_positive_controls(conn, args.species, args.positives)
    neg = select_negative_controls(conn, args.species, args.negatives)
    print(f"Selected {len(pos)} positive controls, {len(neg)} negative controls", flush=True)

    all_edges = pos + neg
    for i, edge in enumerate(all_edges):
        label = edge["control_type"]
        src = edge.get("source_symbol", edge["source_id"])
        tgt = edge.get("target_symbol", edge["target_id"])
        print(f"[{i+1}/{len(all_edges)}] ({label}) {src} -> {tgt}...", end=" ", flush=True)

        try:
            edge = run_prediction(edge, conn, api_key, args.dna_window)
        except Exception as exc:
            edge["confidence_score"] = None
            edge["binding_class"] = "error"
            edge["error"] = str(exc)[:200]
        all_edges[i] = edge

        score_str = f"{edge['confidence_score']:.4f}" if edge.get("confidence_score") is not None else "n/a"
        print(f"{edge['binding_class']} ({score_str})", flush=True)

        if edge["binding_class"] not in ("no_sequence", "error") and i < len(all_edges) - 1:
            time.sleep(args.rate_limit)

    pos_scores = [e["confidence_score"] for e in all_edges
                  if e["control_type"] == "positive" and e.get("confidence_score") is not None]
    neg_scores = [e["confidence_score"] for e in all_edges
                  if e["control_type"] == "negative" and e.get("confidence_score") is not None]

    def stats(scores):
        if not scores:
            return {"n": 0}
        s = sorted(scores)
        return {
            "n": len(s),
            "min": round(s[0], 4),
            "max": round(s[-1], 4),
            "mean": round(sum(s) / len(s), 4),
            "median": round(s[len(s) // 2], 4),
            "q25": round(s[len(s) // 4], 4),
            "q75": round(s[3 * len(s) // 4], 4),
        }

    separation = None
    if pos_scores and neg_scores:
        pos_mean = sum(pos_scores) / len(pos_scores)
        neg_mean = sum(neg_scores) / len(neg_scores)
        separation = round(pos_mean - neg_mean, 4)

    report = {
        "species": args.species,
        "dna_window": args.dna_window,
        "positive_controls": stats(pos_scores),
        "negative_controls": stats(neg_scores),
        "mean_separation": separation,
        "interpretation": (
            "positive_mean > negative_mean suggests Boltz-2 scores "
            "distinguish real TF-DNA binding from random pairs"
            if separation and separation > 0
            else "no clear separation — thresholds may need adjustment "
                 "or the DNA window/model parameters may need tuning"
        ),
        "current_thresholds": {"likely": 0.7, "uncertain": 0.4},
        "all_results": all_edges,
    }

    out_path = Path(__file__).resolve().parents[1] / "data" / "structural_binding_calibration.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nCalibration report saved to {out_path}")
    print(json.dumps({k: v for k, v in report.items() if k != "all_results"}, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
