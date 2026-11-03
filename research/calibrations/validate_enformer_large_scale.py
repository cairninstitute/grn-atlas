#!/usr/bin/env python3
"""Large-scale Enformer binding validation.

Fixes from the n=20 pilot:
  - Unique target genes in negatives (no duplicate-target bug)
  - n=50+50 per TF where possible
  - Per-TF AUC breakdown
  - Overall AUC via sklearn
  - Intermediate saves after each edge

Runs on local GPU (RTX 5070 Ti). No API keys needed.

Usage:
  nohup python backend/scripts/validate_enformer_large_scale.py \
      --positives 50 --negatives 50 \
      > /tmp/enformer_large_validation.log 2>&1 &
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

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
OUT = Path(__file__).resolve().parents[1] / "data" / "enformer_large_validation.json"
ENFORMER_URL = "https://tfhub.dev/deepmind/enformer/1"
ENFORMER_INPUT_LEN = 393_216
ENFORMER_N_BINS = 896

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import SPECIES_CONFIG, _http_get


def load_track_index() -> dict[str, list[int]]:
    track_file = Path(__file__).resolve().parent / "enformer_human_tracks.json"
    if track_file.exists():
        return json.loads(track_file.read_text())
    raise FileNotFoundError(f"Track index not found at {track_file}")


def fetch_genomic_window(gene_id: str, species: str, conn: sqlite3.Connection,
                         window: int = ENFORMER_INPUT_LEN) -> str | None:
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


def load_enformer():
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
    import tensorflow as tf
    import tensorflow_hub as hub
    print("Loading Enformer model...", flush=True)
    hub_model = hub.load(ENFORMER_URL)
    model = hub_model.model
    print("Enformer loaded.", flush=True)
    return model


def predict_tracks(model, seq: str) -> np.ndarray | None:
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
    return predictions["human"].numpy()[0]


def select_controls(conn: sqlite3.Connection, species: str, max_pos: int,
                    max_neg: int, tf_tracks: dict) -> tuple[list[dict], list[dict]]:
    available_tfs = set(tf_tracks.keys())

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
        if r[1].upper() in available_tfs and r[2] not in used_targets and len(positives) < max_pos:
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


def save_intermediate(report: dict):
    OUT.write_text(json.dumps(report, indent=2, default=str))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Large-scale Enformer binding validation")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="human")
    parser.add_argument("--positives", type=int, default=50)
    parser.add_argument("--negatives", type=int, default=50)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")

    tf_tracks = load_track_index()
    print(f"Enformer TF tracks: {len(tf_tracks)} TFs", flush=True)

    positives, negatives = select_controls(conn, args.species, args.positives,
                                           args.negatives, tf_tracks)
    print(f"Selected {len(positives)} positive, {len(negatives)} negative controls", flush=True)
    print(f"Unique positive targets: {len(set(p['target_id'] for p in positives))}", flush=True)
    print(f"Unique negative targets: {len(set(n['target_id'] for n in negatives))}", flush=True)

    if not positives:
        print("ERROR: No positive controls matched Enformer TFs.")
        return 1

    model = load_enformer()
    all_edges = positives + negatives
    center_bin = ENFORMER_N_BINS // 2
    start_time = time.time()

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

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed * 60
            print(f"  [{i+1}/{len(all_edges)}] {elapsed/60:.1f}min elapsed, {rate:.1f} edges/min", flush=True)
            _save_progress(all_edges, args, i + 1)

    elapsed = time.time() - start_time
    print(f"\nAll {len(all_edges)} edges complete in {elapsed/60:.1f} minutes", flush=True)

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
            "mean_positive": round(np.mean(p), 4) if p else None,
            "mean_negative": round(np.mean(n), 4) if n else None,
            "separation": sep,
            "auc": auc,
            "n_tracks": len(tf_tracks.get(tf, [])),
        }

    def stats(scores):
        if not scores:
            return {"n": 0}
        s = sorted(scores)
        return {
            "n": len(s), "min": round(s[0], 4), "max": round(s[-1], 4),
            "mean": round(np.mean(s), 4), "median": round(np.median(s), 4),
            "std": round(np.std(s), 4),
        }

    report = {
        "validation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "Enformer (DeepMind, TF Hub, local GPU)",
        "species": args.species,
        "input_window": ENFORMER_INPUT_LEN,
        "n_requested": {"positives": args.positives, "negatives": args.negatives},
        "n_scored": {"positives": len(pos_scores), "negatives": len(neg_scores)},
        "unique_targets": {
            "positives": len(set(e["target_id"] for e in all_edges
                                 if e["control_type"] == "positive" and e.get("score") is not None)),
            "negatives": len(set(e["target_id"] for e in all_edges
                                 if e["control_type"] == "negative" and e.get("score") is not None)),
        },
        "overall_auc": overall_auc,
        "positive_controls": stats(pos_scores),
        "negative_controls": stats(neg_scores),
        "mean_separation": round(np.mean(pos_scores) - np.mean(neg_scores), 4) if pos_scores and neg_scores else None,
        "per_tf_results": tf_results,
        "runtime_minutes": round(elapsed / 60, 1),
        "all_results": all_edges,
    }

    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nSaved to {OUT}", flush=True)

    print("\n=== RESULTS ===", flush=True)
    print(f"Overall AUC: {overall_auc}", flush=True)
    print(f"Mean separation: {report['mean_separation']}", flush=True)
    print(f"Positives: {stats(pos_scores)}", flush=True)
    print(f"Negatives: {stats(neg_scores)}", flush=True)
    print(f"\nPer-TF breakdown:", flush=True)
    for tf, r in sorted(tf_results.items(), key=lambda x: x[1].get("separation") or 0, reverse=True):
        print(f"  {tf:10s}: sep={r['separation']:+.3f}  auc={r['auc']}  n={r['n_positive']}+{r['n_negative']}  tracks={r['n_tracks']}", flush=True)

    conn.close()
    return 0


def _save_progress(all_edges, args, done):
    scored = [e for e in all_edges[:done] if e.get("score") is not None]
    pos = [e["score"] for e in scored if e["control_type"] == "positive"]
    neg = [e["score"] for e in scored if e["control_type"] == "negative"]
    partial = {
        "status": "in_progress",
        "edges_done": done,
        "edges_total": len(all_edges),
        "scored_so_far": len(scored),
        "partial_auc": compute_auc(pos, neg),
        "partial_results": all_edges[:done],
    }
    OUT.write_text(json.dumps(partial, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
