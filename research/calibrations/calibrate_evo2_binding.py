#!/usr/bin/env python3
"""Calibrate Evo2 DNA foundation model for binding prediction.

Approach #5: Use Evo2-40B's forward pass to get sequence log-likelihoods
for promoter regions. The hypothesis is that real regulatory promoters
will have higher sequence likelihood than random genomic regions, and
that promoter regions of known TF targets will show distinct patterns.

Evo2 is trained on 9.3 trillion nucleotides across all domains of life,
including plants. Its forward mode returns per-position log probabilities
which we can use to compute sequence plausibility scores.

Usage:
  python backend/scripts/calibrate_evo2_binding.py --species arabidopsis --positives 20 --negatives 20
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


def call_evo2_forward(dna_seq: str, api_key: str, species: str = "arabidopsis") -> dict | None:
    """Call Evo2-40B forward to get sequence embeddings/logits."""
    taxonomy = SPECIES_TAXONOMY.get(species, "")
    sequence = taxonomy + dna_seq if taxonomy else dna_seq

    payload = json.dumps({
        "sequence": sequence,
        "output_layers": ["unembed"],
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
        return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500] if hasattr(e, "read") else ""
        print(f"  Evo2 error {e.code}: {body[:200]}", flush=True)
        return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def extract_score(result: dict) -> float | None:
    """Extract a scalar score from Evo2 forward response.

    The unembed layer returns logits of shape (1, seq_len, vocab_size).
    We compute the mean of the max logit at each position as a proxy
    for how "expected" the sequence is by the model. Higher = more plausible.
    """
    if not result or "error" in result:
        return None

    data = result.get("data")
    if not data or not isinstance(data, str):
        return None

    try:
        decoded = base64.b64decode(data)
        buf = io.BytesIO(decoded)
        npz = np.load(buf, allow_pickle=True)
        key = npz.files[0] if hasattr(npz, "files") else None
        arr = npz[key] if key else npz
        # arr shape: (1, seq_len, vocab_size) — logits
        # Take max logit per position (the model's confidence in the actual token)
        # then mean across positions
        max_logits = arr[0].max(axis=-1)  # (seq_len,)
        return float(np.mean(max_logits))
    except Exception:
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Calibrate Evo2 DNA scoring")
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

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_tables(conn)

    # Test API with a small sequence first
    print("Testing Evo2 API...", flush=True)
    test_result = call_evo2_forward("ATCGATCGATCG", api_key, args.species)
    if test_result and "error" not in test_result:
        print(f"  API OK. Response keys: {list(test_result.keys())}", flush=True)
        test_score = extract_score(test_result)
        print(f"  Test score: {test_score}", flush=True)
    else:
        print(f"  API test failed: {test_result}", flush=True)
        if test_result and "error" in test_result:
            print(f"  Continuing anyway to capture error details...", flush=True)

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
            dna_seq = fetch_promoter_dna(edge["target_id"], args.species, conn, args.dna_window)
        except Exception as e:
            edge["score"] = None
            edge["status"] = "error"
            edge["error"] = f"dna_fetch: {e}"[:200]
            print(f"dna_error: {e}", flush=True)
            continue
        if not dna_seq:
            edge["score"] = None
            edge["status"] = "no_dna"
            print("no_dna", flush=True)
            continue

        try:
            result = call_evo2_forward(dna_seq, api_key, args.species)
            score = extract_score(result)
            edge["score"] = score
            edge["status"] = "scored" if score is not None else "no_score"
            edge["raw_keys"] = list(result.keys()) if result and "error" not in result else None
            if score is not None:
                print(f"score={score:.4f}", flush=True)
            else:
                print(f"no_score (keys: {edge.get('raw_keys')})", flush=True)
        except Exception as e:
            edge["score"] = None
            edge["status"] = "error"
            edge["error"] = str(e)[:200]
            print(f"error: {e}", flush=True)

        if i < len(all_edges) - 1:
            time.sleep(args.rate_limit)

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
        "model": "Evo2-40B",
        "species": args.species,
        "dna_window": args.dna_window,
        "positive_controls": stats(pos_scores),
        "negative_controls": stats(neg_scores),
        "mean_separation": separation,
        "all_results": all_edges,
    }
    out = Path(__file__).resolve().parents[1] / "data" / "evo2_binding_calibration.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nSaved to {out}")
    print(json.dumps({k: v for k, v in report.items() if k != "all_results"}, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
