#!/usr/bin/env python3
"""AgroNT binding calibration.

Tests whether AgroNT (1B param plant DNA foundation model, 6-mer tokenization,
~6144bp max context) embeddings can discriminate known TF-target interactions
from random TF-gene pairs in arabidopsis.

Approach: extract last-hidden-state embeddings for 1000bp promoter windows,
then run L1 logistic regression (same probe approach as Evo2 linear probe).

Note: PlantCaduceus was the first choice but requires mamba_ssm which
cannot compile with CUDA 13.0 / compute 12.0. AgroNT uses standard
transformer architecture.

Usage:
  nohup python backend/scripts/validate_plantcaduceus_binding.py \
      --positives 50 --negatives 50 \
      > /tmp/agront_validation.log 2>&1 &
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
OUT = Path(__file__).resolve().parents[1] / "data" / "agront_validation.json"
WINDOW = 1000

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


def select_controls(conn: sqlite3.Connection, species: str, max_pos: int,
                    max_neg: int) -> tuple[list[dict], list[dict]]:
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
        if r[2] not in used_targets and len(positives) < max_pos:
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


def load_model():
    import torch
    from transformers import AutoTokenizer, AutoModelForMaskedLM

    print("Loading AgroNT tokenizer...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(
        "InstaDeepAI/agro-nucleotide-transformer-1b"
    )
    print("Loading AgroNT model...", flush=True)
    model = AutoModelForMaskedLM.from_pretrained(
        "InstaDeepAI/agro-nucleotide-transformer-1b"
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.half().to(device).eval()
    print(f"AgroNT loaded on {device} (fp16). "
          f"Params: {sum(p.numel() for p in model.parameters()):,}", flush=True)
    return model, tokenizer, device


def extract_embedding(model, tokenizer, device, seq: str) -> np.ndarray | None:
    import torch
    seq = seq[:WINDOW]
    try:
        inputs = tokenizer(seq, return_tensors="pt", padding=True,
                           truncation=True, max_length=1024)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs, output_hidden_states=True)
        last_hidden = outputs.hidden_states[-1]
        embedding = last_hidden.mean(dim=1).squeeze().cpu().float().numpy()
        return embedding
    except Exception as e:
        print(f"  embedding_error: {e}", flush=True)
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AgroNT binding calibration")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="arabidopsis")
    parser.add_argument("--positives", type=int, default=50)
    parser.add_argument("--negatives", type=int, default=50)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")

    positives, negatives = select_controls(conn, args.species, args.positives,
                                           args.negatives)
    print(f"Selected {len(positives)} positive, {len(negatives)} negative controls", flush=True)

    if not positives:
        print("ERROR: No positive controls found.")
        return 1

    model, tokenizer, device = load_model()
    all_edges = positives + negatives
    embeddings = []
    labels = []
    scored_edges = []
    start_time = time.time()

    for i, edge in enumerate(all_edges):
        label = edge["control_type"]
        print(f"[{i+1}/{len(all_edges)}] ({label}) {edge['source_symbol']} -> {edge['target_symbol']}...",
              end=" ", flush=True)

        try:
            seq = fetch_promoter_seq(edge["target_id"], args.species, conn)
        except Exception as e:
            edge["status"] = "error"
            edge["error"] = f"dna_fetch: {e}"[:200]
            print(f"dna_error: {e}", flush=True)
            continue
        if not seq:
            edge["status"] = "no_dna"
            print("no_dna", flush=True)
            continue

        emb = extract_embedding(model, tokenizer, device, seq)
        if emb is None:
            edge["status"] = "error"
            print("embedding_error", flush=True)
            continue

        embeddings.append(emb)
        labels.append(1 if label == "positive" else 0)
        edge["status"] = "scored"
        scored_edges.append(edge)
        print(f"ok (dim={emb.shape[0]})", flush=True)

        if (i + 1) % 20 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed * 60
            print(f"  [{i+1}/{len(all_edges)}] {elapsed/60:.1f}min, {rate:.1f} edges/min", flush=True)

    elapsed = time.time() - start_time
    print(f"\nEmbedding extraction complete: {len(embeddings)} of {len(all_edges)} "
          f"in {elapsed/60:.1f} min", flush=True)

    if len(embeddings) < 10:
        print("ERROR: Too few embeddings for probe analysis.")
        return 1

    X = np.array(embeddings)
    y = np.array(labels)
    print(f"Feature matrix: {X.shape}, pos={sum(y)}, neg={len(y)-sum(y)}", flush=True)

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import cross_val_score

    probe_results = {}
    for C in [0.001, 0.01, 0.1, 1.0, 10.0]:
        clf = LogisticRegression(penalty="l1", C=C, solver="saga",
                                 max_iter=5000, random_state=42)
        scores = cross_val_score(clf, X, y, cv=5, scoring="roc_auc")
        mean_auc = round(float(scores.mean()), 4)
        std_auc = round(float(scores.std()), 4)

        clf.fit(X, y)
        n_nonzero = int(np.sum(clf.coef_ != 0))
        train_auc = round(float(roc_auc_score(y, clf.predict_proba(X)[:, 1])), 4)

        probe_results[str(C)] = {
            "cv_auc_mean": mean_auc,
            "cv_auc_std": std_auc,
            "train_auc": train_auc,
            "n_nonzero_features": n_nonzero,
        }
        print(f"  C={C}: CV-AUC={mean_auc}±{std_auc}, train={train_auc}, "
              f"nonzero={n_nonzero}/{X.shape[1]}", flush=True)

    best_C = max(probe_results, key=lambda c: probe_results[c]["cv_auc_mean"])
    best_auc = probe_results[best_C]["cv_auc_mean"]

    report = {
        "model": "AgroNT-1B",
        "model_source": "InstaDeepAI/agro-nucleotide-transformer-1b",
        "approach": "L1 logistic probe on last-hidden-state mean-pooled embeddings",
        "species": args.species,
        "n_positive": int(sum(y)),
        "n_negative": int(len(y) - sum(y)),
        "embedding_dim": int(X.shape[1]),
        "dna_window_bp": WINDOW,
        "probe_results": probe_results,
        "best_C": float(best_C),
        "best_cv_auc": best_auc,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "edges": all_edges,
    }

    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nResults saved to {OUT}", flush=True)
    print(f"\nAgroNT binding calibration: best CV-AUC = {best_auc} "
          f"(C={best_C})", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
