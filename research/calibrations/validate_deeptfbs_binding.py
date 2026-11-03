#!/usr/bin/env python3
"""deepTFBS binding calibration.

Tests whether deepTFBS per-TF fine-tuned models (CNN+BiLSTM+Attention,
pre-trained on arabidopsis DAP-seq, then transfer-learned per TF) can
discriminate known TF-target interactions from random TF-gene pairs.

Each TF has its own fine-tuned model with a single sigmoid output.
For each edge, we load the TF-specific model and predict binding probability
for the target gene's promoter.

Model weights extracted from Docker image malab/deeptfbs.

Usage:
  nohup python backend/scripts/validate_deeptfbs_binding.py \
      --positives 50 --negatives 50 \
      > /tmp/deeptfbs_validation.log 2>&1 &
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
OUT = Path(__file__).resolve().parents[1] / "data" / "deeptfbs_validation.json"
WINDOW = 1000
PRETRAINED = Path(__file__).resolve().parents[2] / "deepTFBS" / "pretrained_weights" / "1.raw_peak.hdf5"
PER_TF_DIR = Path(__file__).resolve().parents[2] / "deepTFBS" / "pretrained_weights" / "ath"
TF_MAP_FILE = Path(__file__).resolve().parents[2] / "deepTFBS" / "pretrained_weights" / "tf_names.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import SPECIES_CONFIG, _http_get


def fetch_promoter_seq(gene_id: str, species: str, conn: sqlite3.Connection,
                       window: int = WINDOW) -> str | None:
    loc = conn.execute(
        "SELECT chromosome, start, end, strand FROM gene_locations WHERE gene_id=? AND species=?",
        (gene_id, species),
    ).fetchone()
    if not loc:
        return None
    chrom, g_start, g_end, strand = loc
    tss = g_start if strand >= 0 else g_end
    half = window // 2
    start = max(1, tss - half)
    end = tss + half

    cfg = SPECIES_CONFIG.get(species, {})
    ensembl_species = cfg.get("ensembl")
    if not ensembl_species:
        return None

    region = f"{chrom}:{start}..{end}:1"
    url = f"https://rest.ensembl.org/sequence/region/{ensembl_species}/{region}?content-type=text/plain"

    for attempt in range(3):
        seq = _http_get(url)
        if seq and seq.strip() and not seq.strip().startswith("{"):
            clean = seq.strip().upper()
            if strand < 0:
                complement = str.maketrans("ACGT", "TGCA")
                clean = clean.translate(complement)[::-1]
            return clean
        time.sleep(0.5 * (attempt + 1))
    return None


def one_hot_encode(seq: str) -> np.ndarray:
    mapping = {"A": 0, "C": 1, "G": 2, "T": 3}
    arr = np.zeros((len(seq), 4), dtype=np.float32)
    for i, base in enumerate(seq):
        if base in mapping:
            arr[i, mapping[base]] = 1.0
    return arr


def build_pretrained_model():
    """Build multi-task model (359 outputs) and load pretrained weights."""
    import tensorflow as tf
    from tensorflow.keras.layers import (
        Input, Convolution1D, BatchNormalization, Activation, Add,
        AveragePooling1D, Bidirectional, LSTM, Attention,
        GlobalAveragePooling1D, Dropout, Dense
    )
    from tensorflow.keras.models import Model

    def identity_block(x):
        conv1 = Convolution1D(256, 1, kernel_initializer='glorot_normal', padding='same')(x)
        conv1 = BatchNormalization()(conv1)
        conv1 = Activation('relu')(conv1)
        conv2 = Convolution1D(128, 3, kernel_initializer='glorot_normal', padding='same')(conv1)
        conv2 = BatchNormalization()(conv2)
        conv2 = Activation('relu')(conv2)
        conv3 = Convolution1D(256, 1, kernel_initializer='glorot_normal', padding='same')(conv2)
        conv3 = BatchNormalization()(conv3)
        conv3 = Activation('relu')(conv3)
        conv4 = Convolution1D(512, 3, kernel_initializer='glorot_normal', padding='same')(conv3)
        conv4 = BatchNormalization()(conv4)
        conv4 = Activation('relu')(conv4)
        out = Add()([conv4, x])
        return Activation('relu')(out)

    input1 = Input(shape=(WINDOW, 4))
    tfbs = Convolution1D(512, 8, kernel_initializer='glorot_normal', strides=1)(input1)
    tfbs = BatchNormalization()(tfbs)
    tfbs = Activation('relu')(tfbs)
    tfbs = identity_block(tfbs)
    tfbs = AveragePooling1D(pool_size=3)(tfbs)
    bilstm = Bidirectional(LSTM(256, return_sequences=True), merge_mode='concat')(tfbs)
    att = Attention()([bilstm, bilstm, bilstm])
    att = GlobalAveragePooling1D()(att)
    out = Dropout(0.5)(att)
    out = Dense(512, activation='relu')(out)
    out = Dropout(0.5)(out)
    out = Dense(359, activation='sigmoid')(out)

    model = Model(input1, out)
    return model


def build_per_tf_model(pretrained_model):
    """Build per-TF model by modifying pretrained architecture.

    The predict.py code:
    1. Loads pretrained weights
    2. Takes output from layer index 23 (after GlobalAveragePooling)
    3. Adds Dropout + Dense(1, sigmoid) for per-TF prediction
    """
    import tensorflow as tf
    from tensorflow.keras.layers import Dropout, Dense
    from tensorflow.keras.models import Model

    # Get the intermediate output (after attention pooling, before final dense layers)
    intermediate = pretrained_model.get_layer(index=23).output
    out = Dropout(0.5)(intermediate)
    out = Dense(1, activation='sigmoid')(out)
    custom_model = Model(inputs=pretrained_model.input, outputs=out)
    return custom_model


def load_tf_model(tf_agi: str, pretrained_model):
    """Load per-TF fine-tuned model."""
    weights_file = PER_TF_DIR / f"{tf_agi}_rep_0_best_model.hdf5"
    if not weights_file.exists():
        return None

    model = build_per_tf_model(pretrained_model)
    try:
        model.load_weights(str(weights_file))
        return model
    except Exception as e:
        print(f"  weight_load_error for {tf_agi}: {e}", flush=True)
        return None


def select_controls(conn: sqlite3.Connection, species: str, max_pos: int,
                    max_neg: int, available_tfs: set) -> tuple[list[dict], list[dict]]:
    rows = conn.execute("""
        SELECT i.source_id, gs.symbol, i.target_id, gt.symbol, i.confidence
        FROM interactions i
        JOIN genes gs ON gs.id = i.source_id AND gs.species = ? AND gs.is_tf = 1
        JOIN genes gt ON gt.id = i.target_id AND gt.species = ?
        JOIN gene_locations gl ON gl.gene_id = i.target_id
        WHERE i.sign_evidence = 'measured' AND i.confidence >= 0.5
        ORDER BY RANDOM()
    """, (species, species)).fetchall()

    positives = []
    used_targets = set()
    for r in rows:
        if r[0] in available_tfs and r[2] not in used_targets and len(positives) < max_pos:
            positives.append({
                "source_id": r[0], "source_symbol": r[1],
                "target_id": r[2], "target_symbol": r[3],
                "species": species, "control_type": "positive",
            })
            used_targets.add(r[2])

    existing = set()
    for row in conn.execute("SELECT source_id, target_id FROM interactions"):
        existing.add((row[0], row[1]))

    neg_targets = conn.execute("""
        SELECT g.id, g.symbol FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id
        WHERE g.species = ? AND g.is_tf = 0
        ORDER BY RANDOM() LIMIT ?
    """, (species, max_neg * 10)).fetchall()

    negatives = []
    used_neg_targets = set()
    tf_list = [(p["source_id"], p["source_symbol"]) for p in positives]
    random.shuffle(tf_list)
    random.shuffle(neg_targets)

    for tf_id, tf_sym in tf_list:
        for tgt_id, tgt_sym in neg_targets:
            if (tf_id, tgt_id) not in existing and tgt_id not in used_neg_targets and tf_id != tgt_id:
                negatives.append({
                    "source_id": tf_id, "source_symbol": tf_sym,
                    "target_id": tgt_id, "target_symbol": tgt_sym,
                    "species": species, "control_type": "negative",
                })
                used_neg_targets.add(tgt_id)
                break
        if len(negatives) >= max_neg:
            break

    return positives, negatives


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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="deepTFBS binding calibration")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="arabidopsis")
    parser.add_argument("--positives", type=int, default=50)
    parser.add_argument("--negatives", type=int, default=50)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")

    # Load TF mapping
    if TF_MAP_FILE.exists():
        tf_map = json.loads(TF_MAP_FILE.read_text())
    else:
        print("ERROR: TF map file not found. Run Docker extraction first.", flush=True)
        return 1

    available_tfs = set()
    gene_to_agi = {}
    for agi, info in tf_map.items():
        weights = PER_TF_DIR / f"{agi}_rep_0_best_model.hdf5"
        if weights.exists():
            available_tfs.add(info["gene_id"])
            gene_to_agi[info["gene_id"]] = agi

    print(f"deepTFBS available TFs with models: {len(available_tfs)}", flush=True)

    positives, negatives = select_controls(conn, args.species, args.positives,
                                           args.negatives, available_tfs)
    print(f"Selected {len(positives)} positive, {len(negatives)} negative controls", flush=True)

    if not positives:
        print("ERROR: No positive controls found.")
        return 1

    # Build pretrained model architecture (load weights once)
    print("Building pretrained model architecture...", flush=True)
    pretrained = build_pretrained_model()
    print(f"Loading pretrained weights from {PRETRAINED}...", flush=True)
    pretrained.load_weights(str(PRETRAINED))
    print(f"Pretrained model ready. Params: {pretrained.count_params():,}", flush=True)

    all_edges = positives + negatives
    model_cache = {}
    start_time = time.time()

    for i, edge in enumerate(all_edges):
        tf_id = edge["source_id"]
        tf_agi = gene_to_agi.get(tf_id, "")
        label = edge["control_type"]
        print(f"[{i+1}/{len(all_edges)}] ({label}) {edge['source_symbol']} ({tf_agi}) -> {edge['target_symbol']}...",
              end=" ", flush=True)

        # Load or cache per-TF model
        if tf_agi not in model_cache:
            model = load_tf_model(tf_agi, pretrained)
            model_cache[tf_agi] = model
        else:
            model = model_cache[tf_agi]

        if model is None:
            edge["score"] = None
            edge["status"] = "no_model"
            print("no_model", flush=True)
            continue

        try:
            seq = fetch_promoter_seq(edge["target_id"], args.species, conn)
        except Exception as e:
            edge["score"] = None
            edge["status"] = "error"
            edge["error"] = f"dna_fetch: {e}"[:200]
            print(f"dna_error: {e}", flush=True)
            continue
        if not seq:
            edge["score"] = None
            edge["status"] = "no_dna"
            print("no_dna", flush=True)
            continue

        if len(seq) < WINDOW:
            seq = seq + "N" * (WINDOW - len(seq))
        elif len(seq) > WINDOW:
            excess = len(seq) - WINDOW
            seq = seq[excess // 2: excess // 2 + WINDOW]

        encoded = one_hot_encode(seq)
        encoded = np.expand_dims(encoded, 0)

        try:
            pred = model.predict(encoded, verbose=0)
            score = float(pred[0][0])
            edge["score"] = score
            edge["tf_agi"] = tf_agi
            edge["status"] = "scored"
            print(f"score={score:.4f}", flush=True)
        except Exception as e:
            edge["score"] = None
            edge["status"] = "error"
            edge["error"] = str(e)[:200]
            print(f"error: {e}", flush=True)

        if (i + 1) % 20 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed * 60
            print(f"  [{i+1}/{len(all_edges)}] {elapsed/60:.1f}min, {rate:.1f} edges/min", flush=True)

    elapsed = time.time() - start_time
    print(f"\nAll {len(all_edges)} edges complete in {elapsed/60:.1f} min", flush=True)

    pos_scores = [e["score"] for e in all_edges
                  if e["control_type"] == "positive" and e.get("score") is not None]
    neg_scores = [e["score"] for e in all_edges
                  if e["control_type"] == "negative" and e.get("score") is not None]

    overall_auc = compute_auc(pos_scores, neg_scores)

    per_tf = defaultdict(lambda: {"positive": [], "negative": []})
    for e in all_edges:
        if e.get("score") is not None:
            tf = e["source_symbol"].upper()
            per_tf[tf][e["control_type"]].append(e["score"])

    tf_results = {}
    for tf, groups in sorted(per_tf.items()):
        p, n = groups["positive"], groups["negative"]
        auc = compute_auc(p, n)
        sep = round(np.mean(p) - np.mean(n), 4) if p and n else None
        tf_results[tf] = {
            "n_positive": len(p),
            "n_negative": len(n),
            "mean_positive": round(float(np.mean(p)), 4) if p else None,
            "mean_negative": round(float(np.mean(n)), 4) if n else None,
            "separation": sep,
            "auc": auc,
        }

    report = {
        "model": "deepTFBS (per-TF fine-tuned)",
        "model_source": "cma2015/deepTFBS (Docker: malab/deeptfbs)",
        "approach": "Per-TF transfer-learned model, single sigmoid binding probability",
        "species": args.species,
        "n_tf_models": len(available_tfs),
        "n_positive": len(pos_scores),
        "n_negative": len(neg_scores),
        "overall_auc": overall_auc,
        "mean_positive": round(float(np.mean(pos_scores)), 4) if pos_scores else None,
        "mean_negative": round(float(np.mean(neg_scores)), 4) if neg_scores else None,
        "per_tf_results": tf_results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_minutes": round(elapsed / 60, 1),
        "edges": all_edges,
    }

    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nResults saved to {OUT}", flush=True)
    print(f"\ndeepTFBS binding calibration: AUC = {overall_auc}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
