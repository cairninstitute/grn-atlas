#!/usr/bin/env python3
"""Calibrate MSA-assisted Boltz-2 structural binding predictions.

Approach #2: Use ColabFold MSA-Search to build multiple sequence alignments
for TF proteins, then feed MSA + DNA into Boltz-2 for improved structure
prediction. Tests whether MSA context helps Boltz-2 distinguish real TF-DNA
binding from random pairs.

Usage:
  python backend/scripts/calibrate_msa_boltz2.py --species arabidopsis --positives 20 --negatives 20
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import (
    ensure_tables, load_api_key, fetch_protein_sequence,
    fetch_promoter_dna, classify_binding, SPECIES_CONFIG, _http_get,
)
from calibrate_structural_binding import (
    select_positive_controls, select_negative_controls,
)

MSA_SEARCH_URL = "https://health.api.nvidia.com/v1/biology/colabfold/msa-search/predict"
BOLTZ2_URL = "https://health.api.nvidia.com/v1/biology/mit/boltz2/predict"


def call_msa_search(protein_seq: str, api_key: str) -> str | None:
    """Call ColabFold MSA-Search NIM to get A3M alignment for a protein."""
    import urllib.request
    import urllib.error

    if len(protein_seq) > 4096:
        protein_seq = protein_seq[:4096]

    payload = json.dumps({"sequence": protein_seq}).encode()
    req = urllib.request.Request(
        MSA_SEARCH_URL,
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
        return result.get("a3m") or result.get("alignment") or result.get("msa")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500] if hasattr(e, 'read') else ""
        print(f"  MSA error {e.code}: {body}", flush=True)
        return None
    except Exception as e:
        print(f"  MSA error: {e}", flush=True)
        return None


def call_boltz2_with_msa(protein_seq: str, msa_a3m: str | None,
                          dna_seq: str, api_key: str) -> dict | None:
    """Call Boltz-2 with optional MSA for the protein chain."""
    import urllib.request
    import urllib.error

    protein_chain = {
        "id": "A",
        "molecule_type": "protein",
        "sequence": protein_seq,
    }
    if msa_a3m:
        protein_chain["msa"] = msa_a3m

    payload = {
        "polymers": [
            protein_chain,
            {"id": "B", "molecule_type": "dna", "sequence": dna_seq},
        ],
        "recycling_steps": 3,
        "sampling_steps": 50,
        "diffusion_samples": 1,
        "output_format": "mmcif",
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BOLTZ2_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500] if hasattr(e, 'read') else ""
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def run_msa_prediction(edge: dict, conn: sqlite3.Connection, api_key: str,
                       dna_window: int, msa_cache: dict) -> dict:
    species = edge["species"]
    source_id = edge["source_id"]
    symbol = edge.get("source_symbol", source_id)

    protein_seq = fetch_protein_sequence(source_id, symbol, species, conn)
    if not protein_seq:
        edge["confidence_score"] = None
        edge["binding_class"] = "no_sequence"
        edge["msa_status"] = "skipped"
        return edge

    dna_seq = fetch_promoter_dna(edge["target_id"], species, conn, dna_window)
    if not dna_seq:
        edge["confidence_score"] = None
        edge["binding_class"] = "no_sequence"
        edge["msa_status"] = "skipped"
        return edge

    if source_id not in msa_cache:
        print("MSA...", end=" ", flush=True)
        msa_a3m = call_msa_search(protein_seq, api_key)
        msa_cache[source_id] = msa_a3m
        if msa_a3m:
            msa_lines = msa_a3m.count("\n")
            print(f"({msa_lines} seqs)", end=" ", flush=True)
        else:
            print("(no MSA)", end=" ", flush=True)
        time.sleep(1)
    else:
        msa_a3m = msa_cache[source_id]

    edge["msa_status"] = "found" if msa_a3m else "not_found"

    result = call_boltz2_with_msa(protein_seq, msa_a3m, dna_seq, api_key)
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
    import argparse
    parser = argparse.ArgumentParser(description="Calibrate MSA-assisted Boltz-2")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="arabidopsis")
    parser.add_argument("--positives", type=int, default=20)
    parser.add_argument("--negatives", type=int, default=20)
    parser.add_argument("--dna-window", type=int, default=200)
    parser.add_argument("--rate-limit", type=float, default=2.0)
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
    msa_cache: dict[str, str | None] = {}

    for i, edge in enumerate(all_edges):
        label = edge["control_type"]
        src = edge.get("source_symbol", edge["source_id"])
        tgt = edge.get("target_symbol", edge["target_id"])
        print(f"[{i+1}/{len(all_edges)}] ({label}) {src} -> {tgt}...", end=" ", flush=True)

        try:
            edge = run_msa_prediction(edge, conn, api_key, args.dna_window, msa_cache)
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
            "n": len(s), "min": round(s[0], 4), "max": round(s[-1], 4),
            "mean": round(sum(s) / len(s), 4), "median": round(s[len(s) // 2], 4),
            "q25": round(s[len(s) // 4], 4), "q75": round(s[3 * len(s) // 4], 4),
        }

    separation = None
    if pos_scores and neg_scores:
        separation = round(sum(pos_scores) / len(pos_scores) - sum(neg_scores) / len(neg_scores), 4)

    report = {
        "model": "MSA-assisted Boltz-2",
        "species": args.species,
        "dna_window": args.dna_window,
        "msa_stats": {
            "total_tfs": len(msa_cache),
            "with_msa": sum(1 for v in msa_cache.values() if v),
            "without_msa": sum(1 for v in msa_cache.values() if not v),
        },
        "positive_controls": stats(pos_scores),
        "negative_controls": stats(neg_scores),
        "mean_separation": separation,
        "all_results": all_edges,
    }
    out = Path(__file__).resolve().parents[1] / "data" / "msa_boltz2_calibration.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nCalibration report saved to {out}")
    print(json.dumps({k: v for k, v in report.items() if k != "all_results"}, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
