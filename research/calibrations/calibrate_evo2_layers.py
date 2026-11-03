#!/usr/bin/env python3
"""Calibrate Evo2 intermediate layer representations for binding prediction.

Instead of using the final unembed logits (which showed no signal), this
explores whether intermediate hidden layers (8192-dim per position) contain
features that distinguish real TF targets from random genes.

Strategy: for each layer, compute a mean-pooled embedding of the promoter DNA,
then measure whether positive controls cluster differently from negatives using
several metrics (L2 norm, variance, top-k feature activation).

Usage:
  python backend/scripts/calibrate_evo2_layers.py --species arabidopsis --positives 20 --negatives 20
"""

from __future__ import annotations

import base64
import io
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
EVO2_URL = "https://health.api.nvidia.com/v1/biology/arc/evo2-40b/forward"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import (
    ensure_tables, load_api_key, fetch_promoter_dna, SPECIES_CONFIG,
)
from calibrate_structural_binding import (
    select_positive_controls, select_negative_controls,
)

SPECIES_TAXONOMY = {
    "arabidopsis": "|D__Viridiplantae;P__Streptophyta;C__Magnoliopsida;O__Brassicales;F__Brassicaceae;G__Arabidopsis;S__Arabidopsis thaliana|",
    "human": "|D__Metazoa;P__Chordata;C__Mammalia;O__Primates;F__Hominidae;G__Homo;S__Homo sapiens|",
    "mouse": "|D__Metazoa;P__Chordata;C__Mammalia;O__Rodentia;F__Muridae;G__Mus;S__Mus musculus|",
    "tomato": "|D__Viridiplantae;P__Streptophyta;C__Magnoliopsida;O__Solanales;F__Solanaceae;G__Solanum;S__Solanum lycopersicum|",
    "rice": "|D__Viridiplantae;P__Streptophyta;C__Liliopsida;O__Poales;F__Poaceae;G__Oryza;S__Oryza sativa|",
}

LAYERS_TO_TEST = ["blocks.10", "blocks.20", "blocks.30", "norm"]


def call_evo2_layer(dna_seq: str, api_key: str, layer: str,
                    species: str = "arabidopsis") -> np.ndarray | None:
    taxonomy = SPECIES_TAXONOMY.get(species, "")
    sequence = taxonomy + dna_seq if taxonomy else dna_seq

    payload = json.dumps({
        "sequence": sequence,
        "output_layers": [layer],
    }).encode()

    req = urllib.request.Request(
        EVO2_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200] if hasattr(e, "read") else ""
        print(f"  Evo2 error {e.code}: {body}", flush=True)
        return None
    except Exception as e:
        print(f"  Evo2 error: {e}", flush=True)
        return None

    data = result.get("data")
    if not data:
        return None

    try:
        decoded = base64.b64decode(data)
        npz = np.load(io.BytesIO(decoded), allow_pickle=True)
        arr = npz[npz.files[0]]
        return arr[0]  # (seq_len, hidden_dim)
    except Exception:
        return None


def compute_features(hidden: np.ndarray) -> dict:
    """Compute multiple scalar features from hidden state matrix (seq_len, 8192)."""
    mean_pool = hidden.mean(axis=0)  # (8192,)
    return {
        "l2_norm": float(np.linalg.norm(mean_pool)),
        "mean_activation": float(np.mean(np.abs(mean_pool))),
        "max_activation": float(np.max(np.abs(mean_pool))),
        "variance": float(np.var(mean_pool)),
        "top10_mean": float(np.sort(np.abs(mean_pool))[-10:].mean()),
        "top50_mean": float(np.sort(np.abs(mean_pool))[-50:].mean()),
        "positive_fraction": float((mean_pool > 0).sum() / len(mean_pool)),
        "sparsity": float((np.abs(mean_pool) < np.std(mean_pool) * 0.1).sum() / len(mean_pool)),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Calibrate Evo2 intermediate layers")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="arabidopsis")
    parser.add_argument("--positives", type=int, default=20)
    parser.add_argument("--negatives", type=int, default=20)
    parser.add_argument("--dna-window", type=int, default=200)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument("--layers", nargs="+", default=LAYERS_TO_TEST)
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
    print(f"Selected {len(pos)} positive, {len(neg)} negative controls", flush=True)
    if not pos:
        print("ERROR: No positive controls found.")
        return 1

    all_edges = pos + neg
    layer_results = {layer: {"positive": [], "negative": []} for layer in args.layers}

    for i, edge in enumerate(all_edges):
        label = edge["control_type"]
        src = edge.get("source_symbol", edge["source_id"])
        tgt = edge.get("target_symbol", edge["target_id"])
        print(f"[{i+1}/{len(all_edges)}] ({label}) {src} -> {tgt}", flush=True)

        try:
            dna_seq = fetch_promoter_dna(edge["target_id"], args.species, conn, args.dna_window)
        except Exception as e:
            print(f"  dna_error: {e}", flush=True)
            continue
        if not dna_seq:
            print("  no_dna", flush=True)
            continue

        for layer in args.layers:
            hidden = call_evo2_layer(dna_seq, api_key, layer, args.species)
            if hidden is None:
                print(f"  {layer}: failed", flush=True)
                continue

            features = compute_features(hidden)
            features["source"] = src
            features["target"] = tgt
            layer_results[layer][label].append(features)
            print(f"  {layer}: l2={features['l2_norm']:.2f} var={features['variance']:.4f} "
                  f"top10={features['top10_mean']:.2f}", flush=True)

            time.sleep(args.rate_limit)

    report = {
        "model": "Evo2-40B intermediate layers",
        "species": args.species,
        "dna_window": args.dna_window,
        "layers": {},
    }

    feature_names = ["l2_norm", "mean_activation", "max_activation", "variance",
                     "top10_mean", "top50_mean", "positive_fraction", "sparsity"]

    print("\n=== Results by layer and feature ===", flush=True)
    for layer in args.layers:
        pos_data = layer_results[layer]["positive"]
        neg_data = layer_results[layer]["negative"]
        if not pos_data or not neg_data:
            print(f"\n{layer}: insufficient data", flush=True)
            continue

        layer_report = {"n_positive": len(pos_data), "n_negative": len(neg_data), "features": {}}
        print(f"\n{layer} ({len(pos_data)} pos, {len(neg_data)} neg):", flush=True)

        for feat in feature_names:
            pv = [d[feat] for d in pos_data]
            nv = [d[feat] for d in neg_data]
            pm, nm = np.mean(pv), np.mean(nv)
            sep = pm - nm
            # Effect size (Cohen's d)
            pooled_std = np.sqrt((np.var(pv) + np.var(nv)) / 2) if np.var(pv) + np.var(nv) > 0 else 1
            cohens_d = sep / pooled_std if pooled_std > 0 else 0

            layer_report["features"][feat] = {
                "pos_mean": round(float(pm), 6),
                "neg_mean": round(float(nm), 6),
                "separation": round(float(sep), 6),
                "cohens_d": round(float(cohens_d), 4),
            }
            marker = " ***" if abs(cohens_d) > 0.5 else " *" if abs(cohens_d) > 0.2 else ""
            print(f"  {feat:20s}  pos={pm:12.4f}  neg={nm:12.4f}  sep={sep:+12.4f}  d={cohens_d:+.3f}{marker}",
                  flush=True)

        report["layers"][layer] = layer_report

    out = Path(__file__).resolve().parents[1] / "data" / "evo2_layers_calibration.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nSaved to {out}", flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
