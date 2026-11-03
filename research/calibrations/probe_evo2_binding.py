#!/usr/bin/env python3
"""Collect Evo2-7B layer-26 embeddings and train a linear probe for TF-DNA binding.

Resumable, self-throttling script that:
1. Collects layer-26 hidden states from Evo2-7B NIM for positive/negative control edges
2. Caches each embedding to disk (NPZ) so progress survives restarts
3. Backs off exponentially on API errors (429, timeout, 5xx)
4. Once enough embeddings are collected, fits a logistic regression probe
5. Reports cross-validated accuracy to determine if layer-26 encodes binding signal

Usage:
  # Collect embeddings (long-running, use nohup):
  nohup python backend/scripts/probe_evo2_binding.py --phase collect \
      --species arabidopsis --positives 250 --negatives 250 2>&1 | tee backend/data/probe_collect.log &

  # Fit probe on whatever embeddings have been collected so far:
  python backend/scripts/probe_evo2_binding.py --phase probe --species arabidopsis

  # Do both (collect then probe):
  python backend/scripts/probe_evo2_binding.py --phase both --species arabidopsis --positives 250 --negatives 250
"""

from __future__ import annotations

import base64
import io
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
CACHE_BASE = Path(__file__).resolve().parents[1] / "data" / "evo2_embeddings"
RESULTS_FILE = Path(__file__).resolve().parents[1] / "data" / "evo2_probe_results.json"
EDGE_MANIFEST = Path(__file__).resolve().parents[1] / "data" / "evo2_probe_manifest.json"

EVO2_ENDPOINTS = {
    "7b": "https://health.api.nvidia.com/v1/biology/arc/evo2-7b/forward",
    "40b": "https://health.api.nvidia.com/v1/biology/arc/evo2-40b/forward",
}
DEFAULT_MODEL = "40b"
LAYER = "blocks.26"
D_MODEL = {"7b": 4096, "40b": 8192}

SPECIES_TAXONOMY = {
    "arabidopsis": "|D__Viridiplantae;P__Streptophyta;C__Magnoliopsida;O__Brassicales;F__Brassicaceae;G__Arabidopsis;S__Arabidopsis thaliana|",
    "human": "|D__Metazoa;P__Chordata;C__Mammalia;O__Primates;F__Hominidae;G__Homo;S__Homo sapiens|",
    "mouse": "|D__Metazoa;P__Chordata;C__Mammalia;O__Rodentia;F__Muridae;G__Mus;S__Mus musculus|",
}

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import (
    ensure_tables, load_api_key, fetch_promoter_dna,
)

# ---------------------------------------------------------------------------
# Throttle state
# ---------------------------------------------------------------------------

MIN_DELAY = 1.0
MAX_DELAY = 300.0
INITIAL_DELAY = 2.0


class Throttle:
    def __init__(self):
        self.delay = INITIAL_DELAY
        self.consecutive_errors = 0
        self.total_calls = 0
        self.total_errors = 0

    def success(self):
        self.consecutive_errors = 0
        self.delay = max(MIN_DELAY, self.delay * 0.8)
        self.total_calls += 1

    def error(self, retryable: bool = True):
        self.consecutive_errors += 1
        self.total_errors += 1
        self.total_calls += 1
        if retryable:
            self.delay = min(MAX_DELAY, self.delay * 2.0)

    def wait(self):
        time.sleep(self.delay)

    def status(self) -> str:
        return (f"delay={self.delay:.1f}s errs={self.consecutive_errors} "
                f"total={self.total_calls} err_rate={self.total_errors}/{self.total_calls}")


# ---------------------------------------------------------------------------
# Edge selection
# ---------------------------------------------------------------------------

def select_positive_edges(conn: sqlite3.Connection, species: str,
                          max_edges: int) -> list[dict]:
    """Select high-confidence edges with curated direct binding evidence."""
    rows = conn.execute("""
        SELECT source_id, target_id, relation_type, confidence, evidence_tier,
               support_class, evidence_sources
        FROM regulatory_edge_candidates
        WHERE species = ?
          AND support_class = 'direct_signed'
        ORDER BY confidence DESC, RANDOM()
        LIMIT ?
    """, (species, max_edges)).fetchall()

    if not rows:
        rows = conn.execute("""
            SELECT i.source_id, i.target_id, i.sign, i.confidence, 'measured', 'interaction', ''
            FROM interactions i
            JOIN genes gs ON gs.id = i.source_id AND gs.species = ? AND gs.is_tf = 1
            JOIN genes gt ON gt.id = i.target_id AND gt.species = ?
            WHERE i.sign_evidence = 'measured' AND i.confidence >= 0.7
            ORDER BY i.confidence DESC, RANDOM()
            LIMIT ?
        """, (species, species, max_edges)).fetchall()

    edges = []
    for r in rows:
        sym_src = conn.execute("SELECT symbol FROM genes WHERE id=?", (r[0],)).fetchone()
        sym_tgt = conn.execute("SELECT symbol FROM genes WHERE id=?", (r[1],)).fetchone()
        edges.append({
            "source_id": r[0], "target_id": r[1],
            "source_symbol": sym_src[0] if sym_src else r[0],
            "target_symbol": sym_tgt[0] if sym_tgt else r[1],
            "relation_type": r[2], "confidence": r[3],
            "label": 1, "control_type": "positive",
        })
    return edges


def select_negative_edges(conn: sqlite3.Connection, species: str,
                          max_edges: int) -> list[dict]:
    """Random TF-gene pairs with no known regulatory relationship."""
    import random

    tfs = conn.execute("""
        SELECT g.id, g.symbol FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id
        WHERE g.species = ? AND g.is_tf = 1
        ORDER BY RANDOM() LIMIT ?
    """, (species, max_edges * 5)).fetchall()

    all_genes = conn.execute("""
        SELECT g.id, g.symbol FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id
        WHERE g.species = ? AND g.is_tf = 0
        ORDER BY RANDOM() LIMIT ?
    """, (species, max_edges * 5)).fetchall()

    known_pairs = set()
    for row in conn.execute("SELECT source_id, target_id FROM interactions"):
        known_pairs.add((row[0], row[1]))
    for row in conn.execute(
        "SELECT source_id, target_id FROM regulatory_edge_candidates WHERE species=?",
        (species,)
    ):
        known_pairs.add((row[0], row[1]))

    random.shuffle(tfs)
    random.shuffle(all_genes)
    negatives = []
    for tf_id, tf_sym in tfs:
        for tgt_id, tgt_sym in all_genes:
            if (tf_id, tgt_id) not in known_pairs and tf_id != tgt_id:
                negatives.append({
                    "source_id": tf_id, "target_id": tgt_id,
                    "source_symbol": tf_sym, "target_symbol": tgt_sym,
                    "relation_type": "unknown", "confidence": 0.0,
                    "label": 0, "control_type": "negative",
                })
                if len(negatives) >= max_edges:
                    return negatives
        if len(negatives) >= max_edges:
            break
    return negatives


# ---------------------------------------------------------------------------
# Embedding cache
# ---------------------------------------------------------------------------

def edge_key(edge: dict) -> str:
    return f"{edge['source_id']}__{edge['target_id']}"


def _cache_dir(model: str = DEFAULT_MODEL) -> Path:
    return CACHE_BASE / model


def cache_path(species: str, edge: dict, model: str = DEFAULT_MODEL) -> Path:
    d = _cache_dir(model) / species
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{edge_key(edge)}.npz"


def is_cached(species: str, edge: dict, model: str = DEFAULT_MODEL) -> bool:
    return cache_path(species, edge, model).exists()


def save_embedding(species: str, edge: dict, embedding: np.ndarray,
                   model: str = DEFAULT_MODEL):
    np.savez_compressed(cache_path(species, edge, model), embedding=embedding,
                        label=edge["label"])


def load_embedding(species: str, edge: dict,
                   model: str = DEFAULT_MODEL) -> tuple[np.ndarray, int] | None:
    p = cache_path(species, edge, model)
    if not p.exists():
        return None
    data = np.load(p)
    return data["embedding"], int(data["label"])


def load_all_cached(species: str, model: str = DEFAULT_MODEL) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Load all cached embeddings for a species. Returns (X, y, keys)."""
    d = _cache_dir(model) / species
    if not d.exists():
        return np.array([]), np.array([]), []
    xs, ys, keys = [], [], []
    for f in sorted(d.glob("*.npz")):
        data = np.load(f)
        xs.append(data["embedding"])
        ys.append(int(data["label"]))
        keys.append(f.stem)
    if not xs:
        return np.array([]), np.array([]), []
    return np.stack(xs), np.array(ys), keys


# ---------------------------------------------------------------------------
# API call with retry
# ---------------------------------------------------------------------------

def call_evo2_layer26(dna_seq: str, api_key: str, species: str,
                      throttle: Throttle,
                      model: str = DEFAULT_MODEL) -> np.ndarray | None:
    taxonomy = SPECIES_TAXONOMY.get(species, "")
    sequence = taxonomy + dna_seq if taxonomy else dna_seq
    url = EVO2_ENDPOINTS[model]

    payload = json.dumps({
        "sequence": sequence,
        "output_layers": [LAYER],
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if model == "7b":
        headers["nvcf-poll-seconds"] = "300"

    max_retries = 5
    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=payload, headers=headers,
                                    method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            code = e.code
            body = ""
            try:
                body = e.read().decode()[:300]
            except Exception:
                pass

            if code == 429:
                throttle.error(retryable=True)
                wait = min(MAX_DELAY, throttle.delay * (attempt + 1))
                print(f"    429 rate-limited, backing off {wait:.0f}s "
                      f"(attempt {attempt+1}/{max_retries})", flush=True)
                time.sleep(wait)
                continue
            elif code in (500, 502, 503, 504):
                throttle.error(retryable=True)
                wait = min(120, 10 * (2 ** attempt))
                print(f"    {code} server error, retry in {wait:.0f}s "
                      f"(attempt {attempt+1}/{max_retries}): {body[:100]}", flush=True)
                time.sleep(wait)
                continue
            else:
                throttle.error(retryable=False)
                print(f"    HTTP {code}: {body[:100]}", flush=True)
                return None

        except (TimeoutError, urllib.error.URLError, OSError) as e:
            throttle.error(retryable=True)
            wait = min(120, 15 * (2 ** attempt))
            print(f"    timeout/network error, retry in {wait:.0f}s "
                  f"(attempt {attempt+1}/{max_retries}): {e}", flush=True)
            time.sleep(wait)
            continue

        # Parse response
        data = result.get("data")
        if not data:
            throttle.error(retryable=False)
            return None

        try:
            decoded = base64.b64decode(data)
            npz = np.load(io.BytesIO(decoded), allow_pickle=True)
            arr = npz[npz.files[0]]
            hidden = arr[0]  # (seq_len, 4096)
            # Mean-pool across positions
            embedding = hidden.mean(axis=0)  # (4096,)
            throttle.success()
            return embedding
        except Exception as exc:
            throttle.error(retryable=False)
            print(f"    parse error: {exc}", flush=True)
            return None

    print(f"    exhausted {max_retries} retries", flush=True)
    return None


# ---------------------------------------------------------------------------
# Phase 1: Collect embeddings
# ---------------------------------------------------------------------------

def phase_collect(args):
    api_key = load_api_key()
    if not api_key:
        print("ERROR: NVIDIA_NIM_API_KEY not set", flush=True)
        return 1

    model = args.model
    print(f"Using Evo2-{model.upper()} forward endpoint", flush=True)

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_tables(conn)

    print(f"Selecting edges for {args.species}...", flush=True)
    pos = select_positive_edges(conn, args.species, args.positives)
    neg = select_negative_edges(conn, args.species, args.negatives)
    all_edges = pos + neg
    print(f"Selected {len(pos)} positive, {len(neg)} negative edges", flush=True)

    # Save manifest for reproducibility
    manifest = {
        "species": args.species,
        "n_positive": len(pos),
        "n_negative": len(neg),
        "edges": [{"source_id": e["source_id"], "target_id": e["target_id"],
                    "label": e["label"], "control_type": e["control_type"],
                    "source_symbol": e.get("source_symbol", ""),
                    "target_symbol": e.get("target_symbol", "")}
                   for e in all_edges],
    }
    EDGE_MANIFEST.write_text(json.dumps(manifest, indent=2))

    # Count already cached
    already = sum(1 for e in all_edges if is_cached(args.species, e, model))
    remaining = len(all_edges) - already
    print(f"Already cached: {already}, remaining: {remaining}", flush=True)

    if remaining == 0:
        print("All embeddings cached. Run --phase probe to fit.", flush=True)
        conn.close()
        return 0

    throttle = Throttle()
    scored = 0
    skipped = 0
    errors = 0
    start_time = time.time()

    for i, edge in enumerate(all_edges):
        if is_cached(args.species, edge, model):
            skipped += 1
            continue

        label = edge["control_type"]
        src = edge.get("source_symbol", edge["source_id"])
        tgt = edge.get("target_symbol", edge["target_id"])
        progress = f"[{already + scored + 1}/{len(all_edges)}]"
        elapsed = time.time() - start_time
        rate = scored / elapsed * 3600 if elapsed > 0 and scored > 0 else 0

        print(f"{progress} ({label}) {src} -> {tgt} [{throttle.status()}] "
              f"[{rate:.0f}/hr]", end=" ", flush=True)

        # Fetch promoter DNA
        try:
            dna_seq = fetch_promoter_dna(edge["target_id"], args.species,
                                         conn, args.dna_window)
        except Exception as e:
            print(f"dna_error: {e}", flush=True)
            errors += 1
            continue
        if not dna_seq:
            print("no_dna", flush=True)
            errors += 1
            continue

        # Wait before API call
        throttle.wait()

        # Call API
        embedding = call_evo2_layer26(dna_seq, api_key, args.species, throttle,
                                      model=model)
        if embedding is None:
            print("api_error", flush=True)
            errors += 1
            # If too many consecutive errors, pause longer
            if throttle.consecutive_errors >= 10:
                pause = 600
                print(f"  10 consecutive errors — pausing {pause}s", flush=True)
                time.sleep(pause)
                throttle.consecutive_errors = 0
                throttle.delay = INITIAL_DELAY
            continue

        save_embedding(args.species, edge, embedding, model)
        scored += 1
        print(f"OK shape={embedding.shape}", flush=True)

        # Periodic progress
        if scored % 25 == 0:
            X, y, _ = load_all_cached(args.species, model)
            n_pos = (y == 1).sum()
            n_neg = (y == 0).sum()
            print(f"\n--- Progress: {n_pos} pos + {n_neg} neg cached, "
                  f"{errors} errors, {rate:.0f}/hr ---\n", flush=True)

    # Final summary
    X, y, _ = load_all_cached(args.species, model)
    n_pos = (y == 1).sum() if len(y) > 0 else 0
    n_neg = (y == 0).sum() if len(y) > 0 else 0
    elapsed = time.time() - start_time
    print(f"\n=== Collection done ===", flush=True)
    print(f"  Scored: {scored}, Errors: {errors}, Skipped (cached): {skipped}", flush=True)
    print(f"  Total cached: {n_pos} pos + {n_neg} neg = {len(y)}", flush=True)
    print(f"  Elapsed: {elapsed/60:.1f} min ({scored/elapsed*3600:.0f}/hr)" if elapsed > 0 else "", flush=True)

    conn.close()
    return 0


# ---------------------------------------------------------------------------
# Phase 2: Fit linear probe
# ---------------------------------------------------------------------------

def phase_probe(args):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    model = args.model
    X, y, keys = load_all_cached(args.species, model)
    n_pos = (y == 1).sum()
    n_neg = (y == 0).sum()
    print(f"Loaded {len(y)} embeddings ({n_pos} pos, {n_neg} neg) "
          f"from {_cache_dir(model) / args.species}", flush=True)

    if n_pos < 10 or n_neg < 10:
        print(f"ERROR: Need at least 10 of each class. Have {n_pos} pos, {n_neg} neg.", flush=True)
        return 1

    n_splits = min(10, min(n_pos, n_neg))
    print(f"\nFitting logistic regression probe (C sweep, {n_splits}-fold CV)...", flush=True)

    results = {"species": args.species, "n_positive": int(n_pos),
               "n_negative": int(n_neg), "n_total": len(y), "models": []}

    for C in [0.001, 0.01, 0.1, 1.0, 10.0]:
        pipe = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=C, max_iter=2000, solver="saga",
                               penalty="l1", class_weight="balanced",
                               random_state=42),
        )
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        scores = cross_val_score(pipe, X, y, cv=cv, scoring="roc_auc")
        acc_scores = cross_val_score(pipe, X, y, cv=cv, scoring="accuracy")

        model_result = {
            "C": C,
            "mean_auc": round(float(scores.mean()), 4),
            "std_auc": round(float(scores.std()), 4),
            "mean_accuracy": round(float(acc_scores.mean()), 4),
            "std_accuracy": round(float(acc_scores.std()), 4),
            "fold_aucs": [round(float(s), 4) for s in scores],
        }
        results["models"].append(model_result)
        print(f"  C={C:8.3f}  AUC={scores.mean():.4f}±{scores.std():.4f}  "
              f"Acc={acc_scores.mean():.4f}±{acc_scores.std():.4f}", flush=True)

    # Best model
    best = max(results["models"], key=lambda m: m["mean_auc"])
    results["best_model"] = best
    results["verdict"] = _verdict(best["mean_auc"])

    # Fit final model on all data and report top features
    best_C = best["C"]
    pipe = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=best_C, max_iter=2000, solver="saga",
                           penalty="l1", class_weight="balanced",
                           random_state=42),
    )
    pipe.fit(X, y)
    coefs = pipe.named_steps["logisticregression"].coef_[0]
    n_nonzero = (np.abs(coefs) > 1e-8).sum()
    top_pos_dims = np.argsort(coefs)[-20:][::-1]
    top_neg_dims = np.argsort(coefs)[:20]

    results["feature_analysis"] = {
        "n_nonzero_features": int(n_nonzero),
        "top_positive_dims": [{"dim": int(d), "coef": round(float(coefs[d]), 6)} for d in top_pos_dims],
        "top_negative_dims": [{"dim": int(d), "coef": round(float(coefs[d]), 6)} for d in top_neg_dims],
    }

    print(f"\nBest: C={best_C} AUC={best['mean_auc']:.4f}", flush=True)
    print(f"Non-zero features (L1): {n_nonzero} / {len(coefs)}", flush=True)
    print(f"\nVerdict: {results['verdict']}", flush=True)

    RESULTS_FILE.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {RESULTS_FILE}", flush=True)
    return 0


def _verdict(auc: float) -> str:
    if auc < 0.55:
        return ("NO SIGNAL — AUC near chance (0.50). Evo2 layer 26 does not encode "
                "TF-DNA binding information. No SAE or downstream model will help.")
    elif auc < 0.65:
        return ("WEAK SIGNAL — AUC slightly above chance. Some binding-correlated "
                "information exists but likely reflects sequence composition, not "
                "specific TF recognition. Not sufficient for production scoring.")
    elif auc < 0.75:
        return ("MODERATE SIGNAL — AUC shows real separation. Layer 26 encodes some "
                "binding-relevant features. A custom SAE or supervised probe could "
                "potentially be trained for production use.")
    else:
        return ("STRONG SIGNAL — AUC shows clear binding discrimination. Layer 26 "
                "representations contain substantial TF-DNA binding information. "
                "Worth investing in a refined classifier or custom SAE.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evo2 layer-26 linear probe for binding")
    parser.add_argument("--phase", choices=["collect", "probe", "both"], default="both")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="arabidopsis")
    parser.add_argument("--positives", type=int, default=250)
    parser.add_argument("--negatives", type=int, default=250)
    parser.add_argument("--dna-window", type=int, default=200)
    parser.add_argument("--model", choices=["7b", "40b"], default=DEFAULT_MODEL,
                        help="Evo2 model size (default: 40b)")
    args = parser.parse_args()

    if args.phase in ("collect", "both"):
        rc = phase_collect(args)
        if rc != 0:
            return rc

    if args.phase in ("probe", "both"):
        rc = phase_probe(args)
        if rc != 0:
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
