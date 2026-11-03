#!/usr/bin/env python3
"""Diagnostic battery for the Goodfire Evo2-7B SAE.

Tests what the SAE features actually encode across multiple discrimination
tasks. Uses local Evo2-7B inference (no NIM API needed).

Requires: PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

Tasks:
  1. Promoter vs coding DNA
  2. Species discrimination (arabidopsis vs human)
  3. Feature-sequence property correlations (GC content, TATA box, etc.)
  4. Positional activation patterns
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import torch

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
SAE_REPO = "Goodfire/Evo-2-Layer-26-Mixed"
SAE_FILE = "sae-layer26-mixed-expansion_8-k_64.pt"
RESULTS_DIR = Path(__file__).resolve().parents[1] / "data"

SPECIES_TAXONOMY = {
    "arabidopsis": "|D__Viridiplantae;P__Streptophyta;C__Magnoliopsida;O__Brassicales;F__Brassicaceae;G__Arabidopsis;S__Arabidopsis thaliana|",
    "human": "|D__Metazoa;P__Chordata;C__Mammalia;O__Primates;F__Hominidae;G__Homo;S__Homo sapiens|",
    "mouse": "|D__Metazoa;P__Chordata;C__Mammalia;O__Rodentia;F__Muridae;G__Mus;S__Mus musculus|",
}

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import ensure_tables

# ---------------------------------------------------------------------------
# Model loading (singleton)
# ---------------------------------------------------------------------------

_evo2 = None
_sae = None
_tax_cache = {}


class BatchTopKTiedSAE(torch.nn.Module):
    def __init__(self, d_in, d_hidden, k):
        super().__init__()
        self.d_in = d_in
        self.d_hidden = d_hidden
        self.k = k
        self.W = torch.nn.Parameter(torch.zeros(d_in, d_hidden))
        self.b_enc = torch.nn.Parameter(torch.zeros(d_hidden))
        self.b_dec = torch.nn.Parameter(torch.zeros(d_in))

    def encode(self, x):
        f = torch.nn.functional.relu(x @ self.W + self.b_enc)
        return self._topk(f)

    def _topk(self, f):
        from math import prod
        *shape, _ = f.shape
        numel = self.k * prod(shape)
        flat = f.flatten()
        topk = torch.topk(flat, min(numel, flat.numel()), dim=-1)
        result = torch.zeros_like(flat).scatter(-1, topk.indices, topk.values)
        return result.reshape(f.shape)


def get_evo2():
    global _evo2
    if _evo2 is None:
        from evo2 import Evo2
        print("Loading Evo2-7B...", flush=True)
        _evo2 = Evo2("evo2_7b")
        print("Evo2-7B loaded.", flush=True)
    return _evo2


def get_sae():
    global _sae
    if _sae is None:
        from huggingface_hub import hf_hub_download
        print("Loading SAE...", flush=True)
        path = hf_hub_download(repo_id=SAE_REPO, filename=SAE_FILE, repo_type="model")
        state = torch.load(path, map_location="cpu", weights_only=True)
        clean = {k.replace("_orig_mod.", "").replace("module.", ""): v
                 for k, v in state.items()}
        _sae = BatchTopKTiedSAE(4096, 32768, 64)
        _sae.load_state_dict(clean)
        _sae.eval()
        print("SAE loaded.", flush=True)
    return _sae


def _tax_len(species: str) -> int:
    if species not in _tax_cache:
        taxonomy = SPECIES_TAXONOMY.get(species, "")
        if taxonomy:
            evo2 = get_evo2()
            _tax_cache[species] = len(evo2.tokenizer.tokenize(taxonomy))
        else:
            _tax_cache[species] = 0
    return _tax_cache[species]


def get_sae_features(dna_seq: str, species: str = "arabidopsis") -> np.ndarray:
    """Get mean-pooled SAE features for a DNA sequence. Returns (32768,)."""
    evo2 = get_evo2()
    sae = get_sae()
    taxonomy = SPECIES_TAXONOMY.get(species, "")
    sequence = taxonomy + dna_seq if taxonomy else dna_seq

    input_ids = torch.tensor(
        evo2.tokenizer.tokenize(sequence), dtype=torch.int
    ).unsqueeze(0).to("cuda:0")

    with torch.no_grad():
        _, embeddings = evo2(
            input_ids, return_embeddings=True, layer_names=["blocks.26"]
        )
        hidden = embeddings["blocks.26"][0].cpu().float()
        dna_hidden = hidden[_tax_len(species):]
        sae_feats = sae.encode(dna_hidden).numpy()

    return sae_feats.mean(axis=0)  # (32768,)


def get_sae_features_positional(dna_seq: str, species: str = "arabidopsis") -> np.ndarray:
    """Get per-position SAE features. Returns (seq_len, 32768)."""
    evo2 = get_evo2()
    sae = get_sae()
    taxonomy = SPECIES_TAXONOMY.get(species, "")
    sequence = taxonomy + dna_seq if taxonomy else dna_seq

    input_ids = torch.tensor(
        evo2.tokenizer.tokenize(sequence), dtype=torch.int
    ).unsqueeze(0).to("cuda:0")

    with torch.no_grad():
        _, embeddings = evo2(
            input_ids, return_embeddings=True, layer_names=["blocks.26"]
        )
        hidden = embeddings["blocks.26"][0].cpu().float()
        dna_hidden = hidden[_tax_len(species):]
        sae_feats = sae.encode(dna_hidden).numpy()

    return sae_feats


# ---------------------------------------------------------------------------
# Sequence fetching helpers
# ---------------------------------------------------------------------------

def fetch_ensembl_sequence(ensembl_species: str, chrom: str, start: int,
                           end: int, strand: int = 1) -> str | None:
    url = (f"https://rest.ensembl.org/sequence/region/{ensembl_species}/"
           f"{chrom}:{start}..{end}:{strand}?content-type=text/plain")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            seq = resp.read().decode().strip()
        if set(seq.upper()) <= {"A", "C", "G", "T", "N"}:
            return seq
    except Exception:
        pass
    return None


def fetch_cds(gene_id: str) -> str | None:
    url = (f"https://rest.ensembl.org/sequence/id/{gene_id}"
           f"?type=cds&multiple_sequences=1&content-type=text/plain")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            seq = resp.read().decode().strip()
        if set(seq.upper()) <= {"A", "C", "G", "T", "N"}:
            return seq
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Task 1: Promoter vs Coding
# ---------------------------------------------------------------------------

def task_promoter_vs_coding(conn, species: str, n: int):
    print("\n" + "=" * 60)
    print("TASK 1: Promoter vs Coding DNA")
    print("=" * 60 + "\n")

    species_ensembl = {"arabidopsis": "arabidopsis_thaliana", "human": "homo_sapiens"}
    ens_sp = species_ensembl.get(species)

    # Promoters from cache
    promoter_rows = conn.execute("""
        SELECT p.gene_id, p.sequence, g.symbol
        FROM promoter_dna_sequences p
        JOIN genes g ON g.id = p.gene_id
        WHERE p.species = ? AND p.fetch_status = 'found' AND length(p.sequence) >= 150
        ORDER BY RANDOM() LIMIT ?
    """, (species, n)).fetchall()

    # Coding sequences from Ensembl
    coding_genes = conn.execute("""
        SELECT g.id, g.symbol
        FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id
        WHERE g.species = ?
        ORDER BY RANDOM() LIMIT ?
    """, (species, n * 3)).fetchall()

    print(f"Scoring {len(promoter_rows)} promoters...", flush=True)
    promoter_vecs = []
    for gid, seq, sym in promoter_rows:
        print(f"  promoter {sym[:15]}...", end=" ", flush=True)
        try:
            vec = get_sae_features(seq[:200], species)
            promoter_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)

    print(f"\nFetching and scoring coding sequences...", flush=True)
    coding_vecs = []
    for gid, sym in coding_genes:
        if len(coding_vecs) >= n:
            break
        cds = fetch_cds(gid)
        if not cds or len(cds) < 200:
            continue
        print(f"  coding {sym[:15]}...", end=" ", flush=True)
        try:
            vec = get_sae_features(cds[:200], species)
            coding_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)
        time.sleep(0.1)

    if len(promoter_vecs) < 5 or len(coding_vecs) < 5:
        print("Not enough data", flush=True)
        return {"error": "insufficient data"}

    return _analyze_two_groups(
        "promoter", np.stack(promoter_vecs),
        "coding", np.stack(coding_vecs),
    )


# ---------------------------------------------------------------------------
# Task 2: Species discrimination
# ---------------------------------------------------------------------------

def task_species(conn, n: int):
    print("\n" + "=" * 60)
    print("TASK 2: Species Discrimination (Arabidopsis vs Human)")
    print("=" * 60 + "\n")

    species_vecs = {}
    for sp in ["arabidopsis", "human"]:
        rows = conn.execute("""
            SELECT p.gene_id, p.sequence, g.symbol
            FROM promoter_dna_sequences p
            JOIN genes g ON g.id = p.gene_id
            WHERE p.species = ? AND p.fetch_status = 'found' AND length(p.sequence) >= 150
            ORDER BY RANDOM() LIMIT ?
        """, (sp, n)).fetchall()

        vecs = []
        for gid, seq, sym in rows:
            print(f"  {sp} {sym[:15]}...", end=" ", flush=True)
            try:
                vec = get_sae_features(seq[:200], sp)
                vecs.append(vec)
                print(f"active={(vec > 0).sum()}", flush=True)
            except Exception as e:
                print(f"error: {e}", flush=True)
        species_vecs[sp] = np.stack(vecs) if vecs else np.array([])
        print(f"  {sp}: {len(vecs)} scored\n", flush=True)

    a = species_vecs.get("arabidopsis", np.array([]))
    b = species_vecs.get("human", np.array([]))
    if len(a) < 5 or len(b) < 5:
        return {"error": "insufficient data"}

    return _analyze_two_groups("arabidopsis", a, "human", b)


# ---------------------------------------------------------------------------
# Task 3: Feature-property correlations
# ---------------------------------------------------------------------------

def gc_content(seq: str) -> float:
    seq = seq.upper()
    return sum(1 for c in seq if c in "GC") / len(seq) if seq else 0.0


def task_property_correlation(conn, species: str, n: int):
    print("\n" + "=" * 60)
    print("TASK 3: Feature-Property Correlations")
    print("=" * 60 + "\n")

    rows = conn.execute("""
        SELECT p.gene_id, p.sequence, g.symbol
        FROM promoter_dna_sequences p
        JOIN genes g ON g.id = p.gene_id
        WHERE p.species = ? AND p.fetch_status = 'found' AND length(p.sequence) >= 150
        ORDER BY RANDOM() LIMIT ?
    """, (species, n * 2)).fetchall()

    vecs, props = [], []
    for gid, seq, sym in rows:
        if len(vecs) >= n:
            break
        seq = seq[:200]
        print(f"  {sym[:15]}...", end=" ", flush=True)
        try:
            vec = get_sae_features(seq, species)
            vecs.append(vec)
            props.append({"gc": gc_content(seq), "len": len(seq)})
            print(f"gc={props[-1]['gc']:.2f}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)

    if len(vecs) < 10:
        return {"error": "insufficient data"}

    X = np.stack(vecs)
    results = {}

    for prop_name in ["gc"]:
        y = np.array([p[prop_name] for p in props])
        y_c = y - y.mean()
        x_c = X - X.mean(axis=0)
        corrs = (x_c.T @ y_c) / (
            np.sqrt((x_c**2).sum(axis=0) + 1e-10) * np.sqrt((y_c**2).sum() + 1e-10)
        )
        top_pos = np.argsort(corrs)[-10:][::-1]
        top_neg = np.argsort(corrs)[:10]
        n_strong = int((np.abs(corrs) > 0.5).sum())
        n_moderate = int(((np.abs(corrs) > 0.3) & (np.abs(corrs) <= 0.5)).sum())

        results[prop_name] = {
            "n_strong_corr": n_strong,
            "n_moderate_corr": n_moderate,
            "max_r": float(corrs.max()),
            "min_r": float(corrs.min()),
            "top_positive": [{"f": int(f), "r": round(float(corrs[f]), 4)} for f in top_pos],
            "top_negative": [{"f": int(f), "r": round(float(corrs[f]), 4)} for f in top_neg],
        }
        print(f"\n  {prop_name}: max_r={corrs.max():.3f}, min_r={corrs.min():.3f}, "
              f"|r|>0.5: {n_strong}, |r|>0.3: {n_moderate}", flush=True)

    return results


# ---------------------------------------------------------------------------
# Task 4: Positional activation patterns
# ---------------------------------------------------------------------------

def task_positional(conn, species: str, n: int):
    print("\n" + "=" * 60)
    print("TASK 4: Positional Activation Patterns")
    print("=" * 60 + "\n")

    rows = conn.execute("""
        SELECT p.gene_id, p.sequence, g.symbol
        FROM promoter_dna_sequences p
        JOIN genes g ON g.id = p.gene_id
        WHERE p.species = ? AND p.fetch_status = 'found' AND length(p.sequence) >= 150
        ORDER BY RANDOM() LIMIT ?
    """, (species, min(n, 5))).fetchall()

    results = {"sequences": []}
    for gid, seq, sym in rows:
        seq = seq[:200]
        print(f"  {sym[:15]}...", end=" ", flush=True)
        try:
            sae_feats = get_sae_features_positional(seq, species)
            # (seq_len, 32768)
            pos_activation = sae_feats.sum(axis=1)
            pos_n_active = (sae_feats > 0).sum(axis=1)

            max_per_feat = sae_feats.max(axis=0)
            top20 = np.argsort(max_per_feat)[-20:][::-1]

            positional_count = 0
            distributed_count = 0
            for f_idx in top20:
                frac = (sae_feats[:, f_idx] > 0).sum() / sae_feats.shape[0]
                if frac < 0.3:
                    positional_count += 1
                elif frac > 0.7:
                    distributed_count += 1

            results["sequences"].append({
                "gene": sym, "seq_len": len(seq), "n_positions": sae_feats.shape[0],
                "mean_active_per_pos": float(pos_n_active.mean()),
                "positional_features": positional_count,
                "distributed_features": distributed_count,
            })
            print(f"positional={positional_count}/20 distributed={distributed_count}/20",
                  flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)

    return results


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def _analyze_two_groups(name_a, mat_a, name_b, mat_b):
    a_mean = mat_a.mean(axis=0)
    b_mean = mat_b.mean(axis=0)
    diff = a_mean - b_mean
    pooled_std = np.sqrt((mat_a.std(axis=0)**2 + mat_b.std(axis=0)**2) / 2 + 1e-10)
    cohens_d = diff / pooled_std

    n_large = int((np.abs(cohens_d) > 0.8).sum())
    n_medium = int(((np.abs(cohens_d) > 0.5) & (np.abs(cohens_d) <= 0.8)).sum())

    # Linear probe
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    X = np.vstack([mat_a, mat_b])
    y = np.array([0] * len(mat_a) + [1] * len(mat_b))
    n_splits = min(5, min(len(mat_a), len(mat_b)))

    best_auc = None
    best_C = None
    auc_results = {}
    if n_splits >= 2:
        for C in [0.001, 0.01, 0.1, 1.0, 10.0]:
            pipe = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=C, max_iter=2000, solver="saga",
                                   penalty="l1", class_weight="balanced",
                                   random_state=42),
            )
            cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
            aucs = cross_val_score(pipe, X, y, cv=cv, scoring="roc_auc")
            auc_results[C] = float(aucs.mean())
            if best_auc is None or aucs.mean() > best_auc:
                best_auc = float(aucs.mean())
                best_C = C
        print(f"  C sweep: {auc_results}", flush=True)
    auc = best_auc

    top_a = np.argsort(cohens_d)[-10:][::-1]
    top_b = np.argsort(cohens_d)[:10]

    verdict = ("STRONG" if (auc and auc > 0.75) else
               "MODERATE" if (auc and auc > 0.65) else
               "WEAK" if (auc and auc > 0.55) else "NONE")

    print(f"\n  {name_a} vs {name_b}: n={len(mat_a)}+{len(mat_b)}, "
          f"AUC={auc:.3f}, |d|>0.8: {n_large}, verdict: {verdict}", flush=True)

    print(f"\n  Top {name_a}-enriched features:", flush=True)
    for f in top_a[:5]:
        print(f"    f/{f:5d}  {name_a}={a_mean[f]:.3f}  {name_b}={b_mean[f]:.3f}  d={cohens_d[f]:+.3f}",
              flush=True)
    print(f"\n  Top {name_b}-enriched features:", flush=True)
    for f in top_b[:5]:
        print(f"    f/{f:5d}  {name_a}={a_mean[f]:.3f}  {name_b}={b_mean[f]:.3f}  d={cohens_d[f]:+.3f}",
              flush=True)

    return {
        f"n_{name_a}": len(mat_a), f"n_{name_b}": len(mat_b),
        "probe_auc": auc, "best_C": best_C, "c_sweep": auc_results,
        "verdict": verdict,
        "features_large_d": n_large, "features_medium_d": n_medium,
        f"top_{name_a}": [{"f": int(f), "d": round(float(cohens_d[f]), 4)} for f in top_a],
        f"top_{name_b}": [{"f": int(f), "d": round(float(cohens_d[f]), 4)} for f in top_b],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Diagnose Evo2 SAE capabilities")
    parser.add_argument("--task", default="all",
                        choices=["all", "promoter_vs_coding", "species", "properties", "positional"])
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="arabidopsis")
    parser.add_argument("--n-samples", type=int, default=15)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_tables(conn)

    all_results = {}
    tasks = {
        "promoter_vs_coding": lambda: task_promoter_vs_coding(conn, args.species, args.n_samples),
        "species": lambda: task_species(conn, args.n_samples),
        "properties": lambda: task_property_correlation(conn, args.species, args.n_samples),
        "positional": lambda: task_positional(conn, args.species, args.n_samples),
    }

    task_list = tasks.keys() if args.task == "all" else [args.task]
    for name in task_list:
        try:
            result = tasks[name]()
            all_results[name] = result
        except Exception as e:
            print(f"\nTASK {name} FAILED: {e}", flush=True)
            import traceback; traceback.print_exc()
            all_results[name] = {"error": str(e)}

    conn.close()

    out = RESULTS_DIR / "evo2_sae_diagnostic.json"
    out.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\n{'=' * 60}")
    print(f"Results saved to {out}")
    print(f"{'=' * 60}")

    print("\nSUMMARY:")
    for name, result in all_results.items():
        if "error" in result:
            print(f"  {name}: FAILED — {result['error']}")
        elif "probe_auc" in result:
            print(f"  {name}: AUC={result['probe_auc']:.3f} ({result.get('verdict', '?')})")
        elif "gc" in result:
            gc = result["gc"]
            print(f"  {name}/gc: max_r={gc['max_r']:.3f}, features |r|>0.5: {gc['n_strong_corr']}")
        else:
            print(f"  {name}: completed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
