#!/usr/bin/env python3
"""Borzoi binding calibration.

Tests whether Borzoi (Enformer successor, 524K bp input, 32bp resolution,
PyTorch) ChIP-seq track predictions discriminate known TF-target interactions
from random TF-gene pairs. Human edges only.

Same approach as validate_enformer_large_scale.py but with Borzoi model:
  - 524,288 bp genomic window centered on target TSS
  - Extract TF-specific ChIP-seq track signal at TSS bins
  - Compare mean signal for positive vs negative controls

Usage:
  nohup python backend/scripts/validate_borzoi_binding.py \
      --positives 50 --negatives 50 \
      > /tmp/borzoi_validation.log 2>&1 &
"""

from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
OUT = Path(__file__).resolve().parents[1] / "data" / "borzoi_validation.json"
BORZOI_INPUT_LEN = 524_288
BORZOI_N_BINS = 6144
TRACK_INDEX = Path(__file__).resolve().parent / "borzoi_human_tracks.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import SPECIES_CONFIG, _http_get


def load_track_index() -> dict[str, list[int]]:
    if TRACK_INDEX.exists():
        return json.loads(TRACK_INDEX.read_text())
    raise FileNotFoundError(f"Track index not found at {TRACK_INDEX}")


def fetch_genomic_window(gene_id: str, species: str, conn: sqlite3.Connection,
                         window: int = BORZOI_INPUT_LEN) -> str | None:
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


def load_borzoi():
    import torch
    from borzoi_pytorch import Borzoi

    print("Loading Borzoi replicate-0...", flush=True)
    model = Borzoi.from_pretrained("johahi/borzoi-replicate-0")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device).eval()
    print(f"Borzoi loaded on {device}. "
          f"Params: {sum(p.numel() for p in model.parameters()):,}", flush=True)
    return model, device


def predict_tracks(model, device, seq: str) -> np.ndarray | None:
    import torch

    if len(seq) < BORZOI_INPUT_LEN:
        pad_total = BORZOI_INPUT_LEN - len(seq)
        pad_left = pad_total // 2
        pad_right = pad_total - pad_left
        seq = "N" * pad_left + seq + "N" * pad_right
    elif len(seq) > BORZOI_INPUT_LEN:
        excess = len(seq) - BORZOI_INPUT_LEN
        seq = seq[excess // 2: excess // 2 + BORZOI_INPUT_LEN]

    encoded = one_hot_encode(seq)
    # Borzoi expects (batch, channels=4, seq_len) — channels first
    tensor = torch.from_numpy(encoded.T).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(tensor)
    # Output shape: (batch, n_tracks, n_bins)
    return output.cpu().numpy()[0]


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


def _save_progress(all_edges, args, n_done):
    scored = [e for e in all_edges if e.get("score") is not None]
    pos_scores = [e["score"] for e in scored if e["control_type"] == "positive"]
    neg_scores = [e["score"] for e in scored if e["control_type"] == "negative"]
    report = {
        "model": "Borzoi (replicate-0)",
        "species": args.species,
        "n_done": n_done,
        "n_scored": len(scored),
        "n_positive_scored": len(pos_scores),
        "n_negative_scored": len(neg_scores),
        "interim_auc": compute_auc(pos_scores, neg_scores),
        "edges": all_edges[:n_done],
    }
    OUT.write_text(json.dumps(report, indent=2, default=str))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Borzoi binding calibration")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="human")
    parser.add_argument("--positives", type=int, default=50)
    parser.add_argument("--negatives", type=int, default=50)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")

    tf_tracks = load_track_index()
    print(f"Borzoi TF tracks: {len(tf_tracks)} TFs", flush=True)

    positives, negatives = select_controls(conn, args.species, args.positives,
                                           args.negatives, tf_tracks)
    print(f"Selected {len(positives)} positive, {len(negatives)} negative controls", flush=True)

    if not positives:
        print("ERROR: No positive controls matched Borzoi TFs.")
        return 1

    model, device = load_borzoi()
    all_edges = positives + negatives
    center_bin = BORZOI_N_BINS // 2
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
            preds = predict_tracks(model, device, seq)
            # preds shape: (n_tracks, n_bins)
            track_indices = tf_tracks.get(tf_sym, [])
            if not track_indices:
                edge["score"] = None
                edge["status"] = "no_tracks"
                print("no_tracks", flush=True)
                continue

            # Extract signal at TSS center bins (±1 bin around center)
            center_scores = preds[track_indices, :][:, center_bin - 1:center_bin + 2]
            tf_signal = float(center_scores.max(axis=1).mean())
            edge["score"] = tf_signal
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
            print(f"  [{i+1}/{len(all_edges)}] {elapsed/60:.1f}min, {rate:.1f} edges/min", flush=True)
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
            "mean_positive": round(float(np.mean(p)), 4) if p else None,
            "mean_negative": round(float(np.mean(n)), 4) if n else None,
            "separation": sep,
            "auc": auc,
        }

    report = {
        "model": "Borzoi (replicate-0, PyTorch)",
        "model_source": "johahi/borzoi-replicate-0",
        "approach": "ChIP-seq track signal at TSS center bins (32bp resolution)",
        "species": args.species,
        "input_window_bp": BORZOI_INPUT_LEN,
        "output_bins": BORZOI_N_BINS,
        "bin_resolution_bp": 32,
        "n_tf_tracks": len(tf_tracks),
        "n_positive": len(pos_scores),
        "n_negative": len(neg_scores),
        "overall_auc": overall_auc,
        "mean_positive": round(float(np.mean(pos_scores)), 4) if pos_scores else None,
        "mean_negative": round(float(np.mean(neg_scores)), 4) if neg_scores else None,
        "mean_separation": round(float(np.mean(pos_scores)) - float(np.mean(neg_scores)), 4) if pos_scores and neg_scores else None,
        "per_tf_results": tf_results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_minutes": round(elapsed / 60, 1),
        "edges": all_edges,
    }

    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nResults saved to {OUT}", flush=True)
    print(f"\nBorzoi binding calibration: AUC = {overall_auc}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
