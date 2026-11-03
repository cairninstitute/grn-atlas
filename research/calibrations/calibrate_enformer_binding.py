#!/usr/bin/env python3
"""Calibrate Enformer TF-binding predictions for human edges.

Approach #3: Use Enformer (DeepMind) to predict TF ChIP-seq signal from DNA
sequence. Enformer outputs 5,313 tracks per 128bp bin; 2,008 of those are
TF-specific ChIP-seq tracks covering 389 unique human TFs. We score the
predicted ChIP signal at the TSS region for the specific TF, comparing
positive controls (measured bindings) vs negative controls.

Enformer input: 393,216bp DNA centered on target gene TSS.
Output: (896, 5313) matrix — 896 bins x 5313 tracks.
We extract the center bin(s) and look at tracks for the source TF.

Human/mouse only — no plant TF ChIP tracks.

Usage:
  python backend/scripts/calibrate_enformer_binding.py --species human --positives 20 --negatives 20
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
ENFORMER_URL = "https://tfhub.dev/deepmind/enformer/1"
ENFORMER_INPUT_LEN = 393_216
ENFORMER_BIN_SIZE = 128
ENFORMER_N_BINS = 896

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import (
    ensure_tables, SPECIES_CONFIG, _http_get,
)


def load_track_index() -> dict[str, list[int]]:
    """Map TF symbol -> list of Enformer output track indices (human ChIP-seq)."""
    track_file = Path(__file__).resolve().parent / "enformer_human_tracks.json"
    if track_file.exists():
        return json.loads(track_file.read_text())

    targets_url = "https://raw.githubusercontent.com/calico/basenji/master/manuscripts/cross2020/targets_human.txt"
    data = _http_get(targets_url)
    if not data:
        print("ERROR: Could not fetch Enformer track list", flush=True)
        return {}

    histone_prefixes = ("H2", "H3", "H4")
    tf_tracks: dict[str, list[int]] = {}
    for line in data.strip().split("\n")[1:]:
        cols = line.split("\t")
        if len(cols) < 8:
            continue
        idx = int(cols[0])
        desc = cols[7]
        if not desc.startswith("CHIP:"):
            continue
        parts = desc.split(":")
        if len(parts) < 2:
            continue
        factor = parts[1].strip()
        if not factor or factor == "." or any(factor.startswith(h) for h in histone_prefixes):
            continue
        tf_tracks.setdefault(factor, []).append(idx)

    track_file.write_text(json.dumps(tf_tracks, indent=2))
    print(f"Saved {len(tf_tracks)} TF track mappings to {track_file}", flush=True)
    return tf_tracks


def fetch_genomic_window(gene_id: str, species: str, conn: sqlite3.Connection,
                         window: int = ENFORMER_INPUT_LEN) -> str | None:
    """Fetch a large genomic window centered on gene TSS from Ensembl."""
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

    seq = _http_get(url)
    if seq and seq.strip() and not seq.strip().startswith("{"):
        clean = seq.strip().upper()
        if strand < 0:
            complement = str.maketrans("ACGT", "TGCA")
            clean = clean.translate(complement)[::-1]
        return clean
    return None


def one_hot_encode(seq: str) -> np.ndarray:
    """One-hot encode DNA: (len, 4) ACGT."""
    mapping = {"A": 0, "C": 1, "G": 2, "T": 3}
    arr = np.zeros((len(seq), 4), dtype=np.float32)
    for i, base in enumerate(seq):
        if base in mapping:
            arr[i, mapping[base]] = 1.0
    return arr


def load_enformer():
    """Load Enformer from TF Hub."""
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
    import tensorflow as tf
    import tensorflow_hub as hub

    print("Loading Enformer model...", flush=True)
    hub_model = hub.load(ENFORMER_URL)
    model = hub_model.model
    print("Enformer loaded.", flush=True)
    return model


def predict_tracks(model, seq: str) -> np.ndarray | None:
    """Run Enformer on a DNA sequence, return human track predictions."""
    import tensorflow as tf

    if len(seq) < ENFORMER_INPUT_LEN:
        pad_total = ENFORMER_INPUT_LEN - len(seq)
        pad_left = pad_total // 2
        pad_right = pad_total - pad_left
        seq = "N" * pad_left + seq + "N" * pad_right
    elif len(seq) > ENFORMER_INPUT_LEN:
        excess = len(seq) - ENFORMER_INPUT_LEN
        seq = seq[excess // 2: excess // 2 + ENFORMER_INPUT_LEN]

    encoded = one_hot_encode(seq)
    encoded = tf.cast(tf.expand_dims(encoded, 0), tf.float32)

    predictions = model.predict_on_batch(encoded)
    human_preds = predictions["human"].numpy()
    return human_preds[0]


def select_controls(conn: sqlite3.Connection, species: str, max_each: int,
                    tf_tracks: dict) -> tuple[list[dict], list[dict]]:
    """Select positive/negative controls where source TF has Enformer tracks."""
    import random

    available_tfs = set(tf_tracks.keys())

    positives = []
    rows = conn.execute("""
        SELECT i.source_id, gs.symbol, i.target_id, gt.symbol, i.confidence
        FROM interactions i
        JOIN genes gs ON gs.id = i.source_id AND gs.species = ? AND gs.is_tf = 1
        JOIN genes gt ON gt.id = i.target_id AND gt.species = ?
        JOIN gene_locations gl ON gl.gene_id = i.target_id
        WHERE i.sign_evidence = 'measured' AND i.confidence >= 0.7
        ORDER BY RANDOM()
    """, (species, species)).fetchall()
    for r in rows:
        if r[1].upper() in available_tfs and len(positives) < max_each:
            positives.append({
                "source_id": r[0], "source_symbol": r[1],
                "target_id": r[2], "target_symbol": r[3],
                "species": species, "control_type": "positive",
            })

    existing = set()
    for row in conn.execute("SELECT source_id, target_id FROM interactions"):
        existing.add((row[0], row[1]))

    neg_targets = conn.execute("""
        SELECT g.id, g.symbol FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id
        WHERE g.species = ? AND g.is_tf = 0
        ORDER BY RANDOM() LIMIT ?
    """, (species, max_each * 5)).fetchall()

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
    parser = argparse.ArgumentParser(description="Calibrate Enformer TF binding")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="human")
    parser.add_argument("--positives", type=int, default=20)
    parser.add_argument("--negatives", type=int, default=20)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_tables(conn)

    tf_tracks = load_track_index()
    print(f"Enformer TF tracks: {len(tf_tracks)} TFs", flush=True)
    if not tf_tracks:
        print("ERROR: No Enformer track mappings.")
        return 1

    positives, negatives = select_controls(conn, args.species, args.positives, tf_tracks)
    print(f"Selected {len(positives)} positive, {len(negatives)} negative controls", flush=True)
    if not positives:
        print("ERROR: No positive controls matched Enformer TFs.")
        return 1

    model = load_enformer()

    all_edges = positives + negatives
    center_bin = ENFORMER_N_BINS // 2

    for i, edge in enumerate(all_edges):
        tf_sym = edge["source_symbol"].upper()
        label = edge["control_type"]
        print(f"[{i+1}/{len(all_edges)}] ({label}) {edge['source_symbol']} -> {edge['target_symbol']}...",
              end=" ", flush=True)

        try:
            seq = fetch_genomic_window(edge["target_id"], args.species, conn)
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

        try:
            preds = predict_tracks(model, seq)
            track_indices = tf_tracks.get(tf_sym, [])
            if not track_indices:
                edge["score"] = None
                edge["status"] = "no_tracks"
                print("no_tracks", flush=True)
                continue

            center_scores = preds[center_bin - 1:center_bin + 2, :]
            tf_signal = np.mean([center_scores[:, idx].max() for idx in track_indices])
            edge["score"] = float(tf_signal)
            edge["status"] = "scored"
            edge["n_tracks"] = len(track_indices)
            print(f"score={tf_signal:.4f} ({len(track_indices)} tracks)", flush=True)
        except Exception as e:
            edge["score"] = None
            edge["status"] = "error"
            edge["error"] = str(e)[:200]
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
        "model": "Enformer",
        "species": args.species,
        "input_window": ENFORMER_INPUT_LEN,
        "positive_controls": stats(pos_scores),
        "negative_controls": stats(neg_scores),
        "mean_separation": separation,
        "all_results": all_edges,
    }
    out = Path(__file__).resolve().parents[1] / "data" / "enformer_binding_calibration.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nSaved to {out}")
    print(json.dumps({k: v for k, v in report.items() if k != "all_results"}, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
