#!/usr/bin/env python3
"""Calibrate Evo2 7B + Goodfire SAE for TF-DNA binding prediction.

Uses the Evo2 7B NIM forward endpoint to extract layer 26 hidden states
(4096-dim), then passes them through the Goodfire BatchTopK SAE to get
32,768 sparse features per position. Tests whether any features
distinguish real TF target promoters from random genomic DNA.

Usage:
  python backend/scripts/calibrate_evo2_sae.py --species arabidopsis --positives 20 --negatives 20
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
import torch

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
EVO2_7B_URL = "https://health.api.nvidia.com/v1/biology/arc/evo2-7b/forward"
SAE_REPO = "Goodfire/Evo-2-Layer-26-Mixed"
SAE_FILE = "sae-layer26-mixed-expansion_8-k_64.pt"
LAYER = "blocks.26"

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


class BatchTopKTiedSAE(torch.nn.Module):
    def __init__(self, d_in, d_hidden, k, device, dtype):
        super().__init__()
        self.d_in = d_in
        self.d_hidden = d_hidden
        self.k = k
        self.W = torch.nn.Parameter(torch.zeros(d_in, d_hidden))
        self.b_enc = torch.nn.Parameter(torch.zeros(d_hidden))
        self.b_dec = torch.nn.Parameter(torch.zeros(d_in))
        self.device = device
        self.dtype = dtype
        self.to(device, dtype)

    def encode(self, x):
        f = torch.nn.functional.relu(x @ self.W + self.b_enc)
        return self._topk(f)

    def _topk(self, f):
        *shape, _ = f.shape
        from math import prod
        numel = self.k * prod(shape)
        flat = f.flatten()
        topk = torch.topk(flat, min(numel, flat.numel()), dim=-1)
        result = torch.zeros_like(flat).scatter(-1, topk.indices, topk.values)
        return result.reshape(f.shape)


def load_sae(device="cpu", dtype=torch.float32):
    from huggingface_hub import hf_hub_download
    path = hf_hub_download(repo_id=SAE_REPO, filename=SAE_FILE, repo_type="model")
    state = torch.load(path, map_location="cpu", weights_only=True)
    clean = {k.replace("_orig_mod.", "").replace("module.", ""): v for k, v in state.items()}
    sae = BatchTopKTiedSAE(4096, 32768, 64, device, dtype)
    sae.load_state_dict(clean)
    sae.eval()
    return sae


def call_evo2_7b_layer26(dna_seq: str, api_key: str, species: str = "arabidopsis") -> np.ndarray | None:
    taxonomy = SPECIES_TAXONOMY.get(species, "")
    sequence = taxonomy + dna_seq if taxonomy else dna_seq

    payload = json.dumps({
        "sequence": sequence,
        "output_layers": [LAYER],
    }).encode()

    req = urllib.request.Request(
        EVO2_7B_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "nvcf-poll-seconds": "300",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200] if hasattr(e, "read") else ""
        print(f"  API error {e.code}: {body}", flush=True)
        return None
    except Exception as e:
        print(f"  API error: {e}", flush=True)
        return None

    data = result.get("data")
    if not data:
        return None

    try:
        decoded = base64.b64decode(data)
        npz = np.load(io.BytesIO(decoded), allow_pickle=True)
        arr = npz[npz.files[0]]
        return arr[0]  # (seq_len, 4096)
    except Exception:
        return None


def extract_sae_features(sae, hidden: np.ndarray) -> np.ndarray:
    with torch.no_grad():
        x = torch.tensor(hidden, dtype=sae.dtype, device=sae.device)
        features = sae.encode(x)
        return features.cpu().numpy()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Calibrate Evo2 7B SAE for binding")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="arabidopsis")
    parser.add_argument("--positives", type=int, default=20)
    parser.add_argument("--negatives", type=int, default=20)
    parser.add_argument("--dna-window", type=int, default=200)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    args = parser.parse_args()

    api_key = load_api_key()
    if not api_key:
        print("ERROR: NVIDIA_NIM_API_KEY not set.")
        return 1

    print("Loading Goodfire SAE...", flush=True)
    sae = load_sae()
    print(f"SAE loaded: {sae.d_in} -> {sae.d_hidden} features, top-k={sae.k}", flush=True)

    print("Testing Evo2 7B API...", flush=True)
    test_hidden = call_evo2_7b_layer26("ATCGATCGATCG", api_key, args.species)
    if test_hidden is not None:
        print(f"  API OK. Hidden shape: {test_hidden.shape}", flush=True)
        test_feats = extract_sae_features(sae, test_hidden)
        n_active = (test_feats > 0).sum()
        print(f"  SAE features: {test_feats.shape}, {n_active} active", flush=True)
    else:
        print("  API test failed.", flush=True)
        return 1

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_tables(conn)

    pos = select_positive_controls(conn, args.species, args.positives)
    neg = select_negative_controls(conn, args.species, args.negatives)
    print(f"Selected {len(pos)} positive, {len(neg)} negative controls", flush=True)

    all_edges = pos + neg
    all_feature_matrices = []

    for i, edge in enumerate(all_edges):
        label = edge["control_type"]
        src = edge.get("source_symbol", edge["source_id"])
        tgt = edge.get("target_symbol", edge["target_id"])
        print(f"[{i+1}/{len(all_edges)}] ({label}) {src} -> {tgt}...", end=" ", flush=True)

        try:
            dna_seq = fetch_promoter_dna(edge["target_id"], args.species, conn, args.dna_window)
        except Exception as e:
            edge["status"] = "error"
            edge["error"] = f"dna_fetch: {e}"[:200]
            all_feature_matrices.append(None)
            print(f"dna_error: {e}", flush=True)
            continue
        if not dna_seq:
            edge["status"] = "no_dna"
            all_feature_matrices.append(None)
            print("no_dna", flush=True)
            continue

        try:
            hidden = call_evo2_7b_layer26(dna_seq, api_key, args.species)
            if hidden is None:
                edge["status"] = "api_error"
                all_feature_matrices.append(None)
                print("api_error", flush=True)
                continue

            features = extract_sae_features(sae, hidden)
            # Mean-pool across positions to get a single feature vector
            feat_vec = features.mean(axis=0)  # (32768,)
            all_feature_matrices.append(feat_vec)

            n_active = (feat_vec > 0).sum()
            top_feat = np.argsort(feat_vec)[-5:][::-1]
            edge["status"] = "scored"
            edge["n_active_features"] = int(n_active)
            edge["top_features"] = [int(f) for f in top_feat]
            edge["top_activations"] = [float(feat_vec[f]) for f in top_feat]
            print(f"active={n_active} top={list(top_feat)}", flush=True)

        except Exception as e:
            edge["status"] = "error"
            edge["error"] = str(e)[:200]
            all_feature_matrices.append(None)
            print(f"error: {e}", flush=True)

        if i < len(all_edges) - 1:
            time.sleep(args.rate_limit)

    # Analyze which features differentiate positive from negative
    pos_vecs = [all_feature_matrices[i] for i in range(len(pos))
                if all_feature_matrices[i] is not None]
    neg_vecs = [all_feature_matrices[len(pos) + i] for i in range(len(neg))
                if len(pos) + i < len(all_feature_matrices) and all_feature_matrices[len(pos) + i] is not None]

    print(f"\n=== Feature analysis: {len(pos_vecs)} pos, {len(neg_vecs)} neg ===", flush=True)

    if pos_vecs and neg_vecs:
        pos_mat = np.stack(pos_vecs)  # (n_pos, 32768)
        neg_mat = np.stack(neg_vecs)  # (n_neg, 32768)

        pos_mean = pos_mat.mean(axis=0)
        neg_mean = neg_mat.mean(axis=0)
        diff = pos_mean - neg_mean

        # Features most enriched in positive controls
        top_pos = np.argsort(diff)[-20:][::-1]
        # Features most enriched in negative controls
        top_neg = np.argsort(diff)[:20]

        # Cohen's d per feature
        pos_std = pos_mat.std(axis=0) + 1e-10
        neg_std = neg_mat.std(axis=0) + 1e-10
        pooled_std = np.sqrt((pos_std**2 + neg_std**2) / 2)
        cohens_d = diff / pooled_std

        # Overall metrics
        pos_total_activation = pos_mat.sum(axis=1).mean()
        neg_total_activation = neg_mat.sum(axis=1).mean()
        pos_n_active = (pos_mat > 0).sum(axis=1).mean()
        neg_n_active = (neg_mat > 0).sum(axis=1).mean()

        print(f"\nGlobal metrics:", flush=True)
        print(f"  Total activation - pos: {pos_total_activation:.2f}, neg: {neg_total_activation:.2f}, "
              f"sep: {pos_total_activation - neg_total_activation:+.2f}", flush=True)
        print(f"  Active features  - pos: {pos_n_active:.1f}, neg: {neg_n_active:.1f}", flush=True)

        print(f"\nTop 20 features enriched in POSITIVE controls (potential regulatory markers):", flush=True)
        for idx in top_pos:
            d = cohens_d[idx]
            marker = " ***" if abs(d) > 0.8 else " **" if abs(d) > 0.5 else " *" if abs(d) > 0.2 else ""
            print(f"  f/{idx:5d}  pos={pos_mean[idx]:.4f}  neg={neg_mean[idx]:.4f}  "
                  f"diff={diff[idx]:+.4f}  d={d:+.3f}{marker}", flush=True)

        print(f"\nTop 20 features enriched in NEGATIVE controls:", flush=True)
        for idx in top_neg:
            d = cohens_d[idx]
            marker = " ***" if abs(d) > 0.8 else " **" if abs(d) > 0.5 else " *" if abs(d) > 0.2 else ""
            print(f"  f/{idx:5d}  pos={pos_mean[idx]:.4f}  neg={neg_mean[idx]:.4f}  "
                  f"diff={diff[idx]:+.4f}  d={d:+.3f}{marker}", flush=True)

        # Count features with significant effect size
        n_large = (np.abs(cohens_d) > 0.8).sum()
        n_medium = ((np.abs(cohens_d) > 0.5) & (np.abs(cohens_d) <= 0.8)).sum()
        n_small = ((np.abs(cohens_d) > 0.2) & (np.abs(cohens_d) <= 0.5)).sum()
        print(f"\nEffect sizes across {len(cohens_d)} features:", flush=True)
        print(f"  Large (|d|>0.8):  {n_large}", flush=True)
        print(f"  Medium (|d|>0.5): {n_medium}", flush=True)
        print(f"  Small (|d|>0.2):  {n_small}", flush=True)

        report_features = {
            "top_positive_features": [
                {"feature_id": int(idx), "pos_mean": float(pos_mean[idx]),
                 "neg_mean": float(neg_mean[idx]), "cohens_d": float(cohens_d[idx])}
                for idx in top_pos
            ],
            "top_negative_features": [
                {"feature_id": int(idx), "pos_mean": float(pos_mean[idx]),
                 "neg_mean": float(neg_mean[idx]), "cohens_d": float(cohens_d[idx])}
                for idx in top_neg
            ],
            "effect_size_counts": {"large": int(n_large), "medium": int(n_medium), "small": int(n_small)},
            "global_metrics": {
                "pos_total_activation": float(pos_total_activation),
                "neg_total_activation": float(neg_total_activation),
                "pos_active_features": float(pos_n_active),
                "neg_active_features": float(neg_n_active),
            },
        }
    else:
        report_features = {}

    report = {
        "model": "Evo2-7B + Goodfire SAE (layer 26)",
        "species": args.species,
        "dna_window": args.dna_window,
        "sae_features": 32768,
        "sae_topk": 64,
        "n_positive": len(pos_vecs),
        "n_negative": len(neg_vecs),
        "feature_analysis": report_features,
        "all_results": all_edges,
    }

    out = Path(__file__).resolve().parents[1] / "data" / "evo2_sae_calibration.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nSaved to {out}", flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
