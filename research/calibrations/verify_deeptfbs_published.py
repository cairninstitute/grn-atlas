#!/usr/bin/env python3
"""Verify deepTFBS per-TF models on their published task: DAP-seq peak classification.

Uses the exact published task definition:
- Positive: 1000bp windows centered on DAP-seq peaks for a given TF
- Negative: Random 1000bp genomic windows with no peak overlap
- Score: per-TF model sigmoid output
- Metric: AUROC

Published result: median AUROC = 0.964 across 359 TFs.

Usage:
  python backend/scripts/verify_deeptfbs_published.py
"""
from __future__ import annotations

import gzip
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["CUDA_VISIBLE_DEVICES"] = ""

GENOME_FA = Path("/tmp/TAIR10_chr4.fa")
PEAKS_DIR = Path("/tmp/dapseq_peaks")
PRETRAINED = Path(__file__).resolve().parents[2] / "deepTFBS" / "pretrained_weights" / "1.raw_peak.hdf5"
PER_TF_DIR = Path(__file__).resolve().parents[2] / "deepTFBS" / "pretrained_weights" / "ath"
TF_MAP_FILE = Path(__file__).resolve().parents[2] / "deepTFBS" / "pretrained_weights" / "tf_names.json"
WINDOW = 1000

TFS_TO_TEST = {
    "LHY": {"agi": "AT1G01060", "peak_file": "LHY.narrowPeak.gz"},
    "HSF3": {"agi": "AT5G16820", "peak_file": "HSF3.narrowPeak.gz"},
    "ABI5": {"agi": "AT2G36270", "peak_file": "ABI5.narrowPeak.gz"},
    "EIN3": {"agi": "AT3G20770", "peak_file": "EIN3.narrowPeak.gz"},
    "WRKY27": {"agi": "AT5G52830", "peak_file": "WRKY27.narrowPeak.gz"},
    "ABF2": {"agi": "AT1G45249", "peak_file": "ABF2.narrowPeak.gz"},
}


def load_genome(fasta_path: Path) -> str:
    print(f"Loading genome from {fasta_path}...", flush=True)
    seq_lines = []
    with open(fasta_path) as f:
        for line in f:
            if not line.startswith(">"):
                seq_lines.append(line.strip())
    seq = "".join(seq_lines).upper()
    print(f"  Loaded {len(seq):,} bp", flush=True)
    return seq


def load_peaks(peak_file: Path, chrom: str = "chr4") -> list[tuple[int, int, int]]:
    peaks = []
    opener = gzip.open if str(peak_file).endswith(".gz") else open
    with opener(peak_file, "rt") as f:
        for line in f:
            parts = line.strip().split("\t")
            if parts[0] == chrom:
                start, end = int(parts[1]), int(parts[2])
                summit = start + int(parts[9]) if len(parts) > 9 else (start + end) // 2
                peaks.append((start, end, summit))
    return peaks


def extract_window(genome: str, center: int, window: int = WINDOW) -> str | None:
    half = window // 2
    start = center - half
    end = center + half
    if start < 0 or end > len(genome):
        return None
    seq = genome[start:end]
    if "N" * 50 in seq:
        return None
    return seq


def one_hot_encode(seq: str) -> np.ndarray:
    mapping = {"A": 0, "C": 1, "G": 2, "T": 3}
    arr = np.zeros((len(seq), 4), dtype=np.float32)
    for i, base in enumerate(seq):
        if base in mapping:
            arr[i, mapping[base]] = 1.0
    return arr


def build_pretrained_model():
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
    return Model(input1, out)


def build_per_tf_model(pretrained_model):
    from tensorflow.keras.layers import Dropout, Dense
    from tensorflow.keras.models import Model
    intermediate = pretrained_model.get_layer(index=23).output
    out = Dropout(0.5)(intermediate)
    out = Dense(1, activation='sigmoid')(out)
    return Model(inputs=pretrained_model.input, outputs=out)


def main():
    genome = load_genome(GENOME_FA)

    print("Building pretrained model...", flush=True)
    pretrained = build_pretrained_model()
    pretrained.load_weights(str(PRETRAINED))
    print(f"Pretrained ready ({pretrained.count_params():,} params)", flush=True)

    n_pos = 200
    n_neg = 200
    results = {}

    for tf_name, tf_info in TFS_TO_TEST.items():
        agi = tf_info["agi"]
        peak_file = PEAKS_DIR / tf_info["peak_file"]

        weights_file = PER_TF_DIR / f"{agi}_rep_0_best_model.hdf5"
        if not weights_file.exists():
            print(f"\n{tf_name} ({agi}): no model weights, skipping", flush=True)
            continue

        peaks = load_peaks(peak_file)
        if len(peaks) < 50:
            print(f"\n{tf_name}: only {len(peaks)} chr4 peaks, skipping", flush=True)
            continue

        print(f"\n{'='*60}", flush=True)
        print(f"{tf_name} ({agi}): {len(peaks)} chr4 peaks", flush=True)

        model = build_per_tf_model(pretrained)
        model.load_weights(str(weights_file))

        # Positive: windows centered on peak summits
        random.shuffle(peaks)
        pos_seqs = []
        peak_regions = set()
        for start, end, summit in peaks:
            seq = extract_window(genome, summit)
            if seq and len(seq) == WINDOW:
                pos_seqs.append(seq)
                for p in range(max(0, summit - WINDOW), summit + WINDOW):
                    peak_regions.add(p)
            if len(pos_seqs) >= n_pos:
                break

        # Negative: random windows NOT overlapping any peak
        neg_seqs = []
        attempts = 0
        while len(neg_seqs) < n_neg and attempts < n_neg * 100:
            center = random.randint(WINDOW, len(genome) - WINDOW)
            if center not in peak_regions:
                seq = extract_window(genome, center)
                if seq and len(seq) == WINDOW:
                    neg_seqs.append(seq)
            attempts += 1

        print(f"  Positives: {len(pos_seqs)}, Negatives: {len(neg_seqs)}", flush=True)

        # Score all sequences
        all_seqs = pos_seqs + neg_seqs
        labels = [1] * len(pos_seqs) + [0] * len(neg_seqs)
        scores = []

        encoded = np.array([one_hot_encode(s) for s in all_seqs])
        preds = model.predict(encoded, batch_size=64, verbose=0)
        scores = [float(p[0]) for p in preds]

        pos_scores = scores[:len(pos_seqs)]
        neg_scores = scores[len(pos_seqs):]

        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score(labels, scores)

        print(f"  Mean positive score: {np.mean(pos_scores):.4f}", flush=True)
        print(f"  Mean negative score: {np.mean(neg_scores):.4f}", flush=True)
        print(f"  Separation: {np.mean(pos_scores) - np.mean(neg_scores):.4f}", flush=True)
        print(f"  AUROC: {auc:.4f}", flush=True)

        results[tf_name] = {
            "agi": agi,
            "n_peaks_chr4": len(peaks),
            "n_positive": len(pos_seqs),
            "n_negative": len(neg_seqs),
            "mean_positive": round(float(np.mean(pos_scores)), 4),
            "mean_negative": round(float(np.mean(neg_scores)), 4),
            "auroc": round(auc, 4),
        }

    print(f"\n{'='*60}", flush=True)
    print("SUMMARY — deepTFBS on published task (DAP-seq peak classification)", flush=True)
    print(f"Published median AUROC: 0.964", flush=True)
    print(f"{'TF':12s} {'AGI':14s} {'Peaks':>6s} {'AUROC':>7s} {'MeanPos':>8s} {'MeanNeg':>8s}", flush=True)
    aucs = []
    for tf, r in sorted(results.items(), key=lambda x: x[1]["auroc"], reverse=True):
        print(f"{tf:12s} {r['agi']:14s} {r['n_peaks_chr4']:6d} {r['auroc']:7.4f} {r['mean_positive']:8.4f} {r['mean_negative']:8.4f}", flush=True)
        aucs.append(r["auroc"])
    if aucs:
        print(f"\nMedian AUROC: {np.median(aucs):.4f} (n={len(aucs)} TFs)", flush=True)

    report = {
        "task": "DAP-seq peak classification (published task)",
        "published_median_auroc": 0.964,
        "our_median_auroc": round(float(np.median(aucs)), 4) if aucs else None,
        "n_tfs_tested": len(aucs),
        "per_tf": results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    out_path = Path(__file__).resolve().parents[1] / "data" / "deeptfbs_published_verification.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nSaved to {out_path}", flush=True)


if __name__ == "__main__":
    main()
