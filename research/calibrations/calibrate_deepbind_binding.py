#!/usr/bin/env python3
"""Calibrate DeepBind TF models for binding prediction.

Uses Kipoi-hosted DeepBind TF models (SELEX-trained, human/mouse) to score
whether a TF's binding motif is present in a target promoter. Compares
positive controls (measured bindings) vs negative controls (random pairs).

DeepBind TF models take a short DNA sequence (~100bp) and output a binding
score for that specific TF. This is closer to motif scanning than structural
prediction, but uses a deep learning model rather than a PWM.

Usage:
  python backend/scripts/calibrate_deepbind_binding.py --species human --positives 20 --negatives 20
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
KIPOI_MODELS = Path.home() / ".kipoi" / "models" / "DeepBind" / "models.tsv"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import (
    ensure_tables, fetch_promoter_dna, SPECIES_CONFIG, _http_get,
)


def load_deepbind_catalog() -> dict[str, list[str]]:
    """Map TF symbol -> list of DeepBind model IDs."""
    if not KIPOI_MODELS.exists():
        return {}
    catalog: dict[str, list[str]] = {}
    for line in KIPOI_MODELS.read_text().splitlines()[1:]:
        cols = line.split("\t")
        model_name = cols[0]
        if "/TF/" not in model_name:
            continue
        parts = model_name.split("/")
        if len(parts) >= 3:
            tf_part = parts[2]
            tf_symbol = tf_part.split("_SELEX_")[-1] if "_SELEX_" in tf_part else tf_part.rsplit("_", 1)[-1]
            if tf_symbol not in catalog:
                catalog[tf_symbol] = []
            catalog[tf_symbol].append(model_name)
    return catalog


def download_deepbind_model(model_name: str) -> tuple[dict | None, np.ndarray | None]:
    """Download and load a DeepBind Keras model architecture + weights."""
    models_tsv = KIPOI_MODELS
    arch_url = None
    weights_url = None
    for line in models_tsv.read_text().splitlines()[1:]:
        cols = line.split("\t")
        if cols[0] == model_name:
            arch_url = cols[5] if len(cols) > 5 else None
            weights_url = cols[6] if len(cols) > 6 else None
            break
    if not arch_url or not weights_url:
        return None, None

    model_dir = Path.home() / ".kipoi" / "models" / "DeepBind" / "model_files"
    model_dir.mkdir(parents=True, exist_ok=True)

    arch_file = model_dir / f"{model_name.replace('/', '-')}.json"
    weights_file = model_dir / f"{model_name.replace('/', '-')}.h5"

    if not arch_file.exists():
        data = _http_get(arch_url, accept="application/json")
        if data:
            arch_file.write_text(data)
    if not weights_file.exists():
        try:
            urllib.request.urlretrieve(weights_url, str(weights_file))
        except Exception:
            return None, None

    try:
        from keras.models import model_from_json
        arch = json.loads(arch_file.read_text())
        model = model_from_json(json.dumps(arch))
        model.load_weights(str(weights_file))
        return model, None
    except Exception as e:
        print(f"  Model load failed: {e}", flush=True)
        return None, None


def one_hot_encode(seq: str) -> np.ndarray:
    """Encode DNA to one-hot: (len, 4) for ACGT."""
    mapping = {"A": 0, "C": 1, "G": 2, "T": 3}
    arr = np.zeros((len(seq), 4), dtype=np.float32)
    for i, base in enumerate(seq.upper()):
        if base in mapping:
            arr[i, mapping[base]] = 1.0
    return arr


def score_sequence(model, seq: str, window: int = 101) -> float:
    """Score a DNA sequence with a DeepBind model, sliding window max."""
    if len(seq) < window:
        encoded = one_hot_encode(seq)
        encoded = np.expand_dims(encoded, 0)
        pred = model.predict(encoded, verbose=0)
        return float(pred.max())

    scores = []
    step = max(1, window // 2)
    for start in range(0, len(seq) - window + 1, step):
        subseq = seq[start:start + window]
        encoded = one_hot_encode(subseq)
        encoded = np.expand_dims(encoded, 0)
        pred = model.predict(encoded, verbose=0)
        scores.append(float(pred.max()))
    return max(scores) if scores else 0.0


def select_controls(conn: sqlite3.Connection, species: str, max_each: int,
                    tf_catalog: dict) -> tuple[list[dict], list[dict]]:
    """Select positive and negative controls where source TF has a DeepBind model."""
    available_tfs = set(tf_catalog.keys())

    positives = []
    rows = conn.execute("""
        SELECT i.source_id, gs.symbol, i.target_id, gt.symbol, i.sign, i.confidence
        FROM interactions i
        JOIN genes gs ON gs.id = i.source_id AND gs.species = ? AND gs.is_tf = 1
        JOIN genes gt ON gt.id = i.target_id AND gt.species = ?
        JOIN gene_locations gl ON gl.gene_id = i.target_id
        WHERE i.sign_evidence = 'measured' AND i.confidence >= 0.7
        ORDER BY RANDOM()
    """, (species, species)).fetchall()
    for r in rows:
        if r[1] in available_tfs and len(positives) < max_each:
            positives.append({
                "source_id": r[0], "source_symbol": r[1],
                "target_id": r[2], "target_symbol": r[3],
                "species": species, "control_type": "positive",
            })

    neg_targets = conn.execute("""
        SELECT g.id, g.symbol FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id
        WHERE g.species = ? AND g.is_tf = 0
        ORDER BY RANDOM() LIMIT ?
    """, (species, max_each * 5)).fetchall()
    existing = set()
    for row in conn.execute("SELECT source_id, target_id FROM interactions"):
        existing.add((row[0], row[1]))

    negatives = []
    tf_list = [(p["source_id"], p["source_symbol"]) for p in positives]
    random.shuffle(neg_targets)
    for tf_id, tf_sym in tf_list:
        for tgt_id, tgt_sym in neg_targets:
            if (tf_id, tgt_id) not in existing and tf_id != tgt_id:
                negatives.append({
                    "source_id": tf_id, "source_symbol": tf_sym,
                    "target_id": tgt_id, "target_symbol": tgt_sym,
                    "species": species, "control_type": "negative",
                })
                break
    return positives, negatives[:max_each]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Calibrate DeepBind TF binding")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="human")
    parser.add_argument("--positives", type=int, default=20)
    parser.add_argument("--negatives", type=int, default=20)
    parser.add_argument("--dna-window", type=int, default=200)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_tables(conn)

    catalog = load_deepbind_catalog()
    print(f"DeepBind TF catalog: {len(catalog)} TFs", flush=True)
    if not catalog:
        print("ERROR: No DeepBind TF models found. Run kipoi first.")
        return 1

    positives, negatives = select_controls(conn, args.species, args.positives, catalog)
    print(f"Selected {len(positives)} positive, {len(negatives)} negative controls", flush=True)

    all_edges = positives + negatives
    model_cache: dict[str, object] = {}

    for i, edge in enumerate(all_edges):
        tf_sym = edge["source_symbol"]
        label = edge["control_type"]
        print(f"[{i+1}/{len(all_edges)}] ({label}) {tf_sym} -> {edge['target_symbol']}...",
              end=" ", flush=True)

        dna_seq = fetch_promoter_dna(edge["target_id"], args.species, conn, args.dna_window)
        if not dna_seq:
            edge["score"] = None
            edge["status"] = "no_dna"
            print("no_dna", flush=True)
            continue

        if tf_sym not in model_cache:
            model_names = catalog.get(tf_sym, [])
            if model_names:
                model, _ = download_deepbind_model(model_names[0])
                model_cache[tf_sym] = model
            else:
                model_cache[tf_sym] = None

        model = model_cache[tf_sym]
        if model is None:
            edge["score"] = None
            edge["status"] = "no_model"
            print("no_model", flush=True)
            continue

        try:
            score = score_sequence(model, dna_seq)
            edge["score"] = score
            edge["status"] = "scored"
            print(f"score={score:.4f}", flush=True)
        except Exception as e:
            edge["score"] = None
            edge["status"] = "error"
            edge["error"] = str(e)[:100]
            print(f"error: {e}", flush=True)

    pos_scores = [e["score"] for e in all_edges
                  if e["control_type"] == "positive" and e.get("score") is not None]
    neg_scores = [e["score"] for e in all_edges
                  if e["control_type"] == "negative" and e.get("score") is not None]

    def stats(scores):
        if not scores:
            return {"n": 0}
        s = sorted(scores)
        return {
            "n": len(s), "min": round(s[0], 4), "max": round(s[-1], 4),
            "mean": round(sum(s) / len(s), 4), "median": round(s[len(s) // 2], 4),
        }

    separation = None
    if pos_scores and neg_scores:
        separation = round(sum(pos_scores) / len(pos_scores) - sum(neg_scores) / len(neg_scores), 4)

    report = {
        "model": "DeepBind",
        "species": args.species,
        "positive_controls": stats(pos_scores),
        "negative_controls": stats(neg_scores),
        "mean_separation": separation,
        "all_results": all_edges,
    }
    out = Path(__file__).resolve().parents[1] / "data" / "deepbind_binding_calibration.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nSaved to {out}")
    print(json.dumps({k: v for k, v in report.items() if k != "all_results"}, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
