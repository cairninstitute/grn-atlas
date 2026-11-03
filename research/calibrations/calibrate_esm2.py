#!/usr/bin/env python3
"""ESM2 protein language model calibration.

Tests what ESM2 embeddings can discriminate in our data:
1. TF vs non-TF classification (all 8 species)
2. TF family classification (can embeddings group TFs by family?)
3. Cross-species TF ortholog similarity

Uses ESM2-650M (facebook/esm2_t33_650M_UR50D), 650M params, 33 layers.
Extracts mean-pooled last-hidden-state embeddings for protein sequences.

Usage:
  python backend/scripts/calibrate_esm2.py > /tmp/esm2_calibration.log 2>&1
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

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
OUT = Path(__file__).resolve().parents[1] / "data" / "esm2_calibration.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import SPECIES_CONFIG


def fetch_protein_seq_uniprot(gene_symbol: str, species: str) -> str | None:
    import urllib.request
    cfg = SPECIES_CONFIG.get(species, {})
    taxon = cfg.get("taxon_id")
    if not taxon:
        return None
    url = (f"https://rest.uniprot.org/uniprotkb/search?"
           f"query=gene:{gene_symbol}+AND+taxonomy_id:{taxon}&format=fasta&size=1")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode()
        lines = [l for l in text.strip().split("\n") if not l.startswith(">")]
        seq = "".join(lines).strip()
        return seq if len(seq) > 20 else None
    except Exception:
        return None


def load_model():
    import torch
    from transformers import AutoTokenizer, AutoModel
    print("Loading ESM2-650M...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D")
    model = AutoModel.from_pretrained("facebook/esm2_t33_650M_UR50D")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.half().to(device).eval()
    params = sum(p.numel() for p in model.parameters())
    print(f"ESM2 loaded on {device} (fp16). Params: {params:,}", flush=True)
    return model, tokenizer, device


def extract_embedding(model, tokenizer, device, seq: str, max_len: int = 1022) -> np.ndarray | None:
    import torch
    seq = seq[:max_len]
    try:
        inputs = tokenizer(seq, return_tensors="pt", padding=True,
                           truncation=True, max_length=max_len + 2)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        emb = outputs.last_hidden_state.mean(dim=1).squeeze().cpu().float().numpy()
        return emb
    except Exception as e:
        print(f"  embedding error: {e}", flush=True)
        return None


def run_probe(X, y, task_name: str) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score, accuracy_score
    from sklearn.model_selection import cross_val_score, StratifiedKFold

    print(f"\n  Probe: {task_name} (n={len(y)}, pos={sum(y)}, neg={len(y)-sum(y)})", flush=True)
    results = {}
    for C in [0.01, 0.1, 1.0, 10.0]:
        clf = LogisticRegression(penalty="l1", C=C, solver="saga",
                                 max_iter=5000, random_state=42)
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        try:
            scores = cross_val_score(clf, X, y, cv=cv, scoring="roc_auc")
            mean_auc = round(float(scores.mean()), 4)
            std_auc = round(float(scores.std()), 4)
            clf.fit(X, y)
            n_nonzero = int(np.sum(clf.coef_ != 0))
            train_pred = clf.predict_proba(X)[:, 1]
            train_auc = round(float(roc_auc_score(y, train_pred)), 4)
            train_acc = round(float(accuracy_score(y, clf.predict(X))), 4)
            results[str(C)] = {
                "cv_auc_mean": mean_auc, "cv_auc_std": std_auc,
                "train_auc": train_auc, "train_acc": train_acc,
                "n_nonzero": n_nonzero,
            }
            print(f"    C={C}: CV-AUC={mean_auc}±{std_auc}, train={train_auc}, "
                  f"nonzero={n_nonzero}/{X.shape[1]}", flush=True)
        except Exception as e:
            print(f"    C={C}: error: {e}", flush=True)

    if results:
        best_C = max(results, key=lambda c: results[c]["cv_auc_mean"])
        best = results[best_C]
        print(f"    Best: C={best_C}, CV-AUC={best['cv_auc_mean']}", flush=True)
        return {"task": task_name, "probe_results": results,
                "best_C": float(best_C), "best_cv_auc": best["cv_auc_mean"]}
    return {"task": task_name, "error": "no results"}


def main():
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA journal_mode=WAL")

    model, tokenizer, device = load_model()
    report = {"model": "ESM2-650M", "tasks": {}, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # =========================================
    # Task 1: TF vs non-TF (per species)
    # =========================================
    print("\n" + "=" * 60, flush=True)
    print("TASK 1: TF vs non-TF classification", flush=True)

    for species in ["arabidopsis", "human", "mouse", "tomato", "rice", "petunia"]:
        print(f"\n--- {species} ---", flush=True)
        n_per_class = 50

        tfs = conn.execute(
            "SELECT id, symbol FROM genes WHERE species=? AND is_tf=1 ORDER BY RANDOM() LIMIT ?",
            (species, n_per_class)
        ).fetchall()
        non_tfs = conn.execute(
            "SELECT id, symbol FROM genes WHERE species=? AND is_tf=0 ORDER BY RANDOM() LIMIT ?",
            (species, n_per_class)
        ).fetchall()

        embeddings, labels, symbols = [], [], []
        all_genes = [(g, 1) for g in tfs] + [(g, 0) for g in non_tfs]

        for i, ((gene_id, symbol), label) in enumerate(all_genes):
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(all_genes)}]", flush=True)
            seq = fetch_protein_seq_uniprot(symbol, species)
            if not seq:
                continue
            emb = extract_embedding(model, tokenizer, device, seq)
            if emb is not None:
                embeddings.append(emb)
                labels.append(label)
                symbols.append(symbol)
            time.sleep(0.2)

        if len(embeddings) < 20:
            print(f"  Too few embeddings ({len(embeddings)}), skipping", flush=True)
            continue

        X = np.array(embeddings)
        y = np.array(labels)
        print(f"  Collected {len(embeddings)} embeddings (dim={X.shape[1]})", flush=True)

        result = run_probe(X, y, f"tf_vs_nontf_{species}")
        result["n_total"] = len(y)
        result["n_tf"] = int(sum(y))
        result["n_nontf"] = int(len(y) - sum(y))
        result["species"] = species
        report["tasks"][f"tf_vs_nontf_{species}"] = result

    # =========================================
    # Task 2: TF family classification (arabidopsis)
    # =========================================
    print("\n" + "=" * 60, flush=True)
    print("TASK 2: TF family classification (arabidopsis)", flush=True)

    # Get TF families from interactions table metadata or gene symbols
    # Use a simpler approach: classify major TF family prefixes
    families = {
        "WRKY": "WRKY%", "MYB": "MYB%", "bHLH": "bHLH%",
        "ERF": "ERF%", "NAC": "NAC%", "bZIP": "bZIP%",
    }

    family_embeddings = {}
    for fam_name, pattern in families.items():
        genes = conn.execute(
            "SELECT id, symbol FROM genes WHERE species='arabidopsis' AND is_tf=1 AND symbol LIKE ? ORDER BY RANDOM() LIMIT 20",
            (pattern,)
        ).fetchall()
        embs = []
        for gene_id, symbol in genes:
            seq = fetch_protein_seq_uniprot(symbol, "arabidopsis")
            if seq:
                emb = extract_embedding(model, tokenizer, device, seq)
                if emb is not None:
                    embs.append(emb)
            time.sleep(0.2)
        if embs:
            family_embeddings[fam_name] = embs
            print(f"  {fam_name}: {len(embs)} embeddings", flush=True)

    # Pairwise family discrimination
    fam_results = {}
    fam_names = list(family_embeddings.keys())
    for i in range(len(fam_names)):
        for j in range(i + 1, len(fam_names)):
            f1, f2 = fam_names[i], fam_names[j]
            e1, e2 = family_embeddings[f1], family_embeddings[f2]
            if len(e1) < 5 or len(e2) < 5:
                continue
            X = np.array(e1 + e2)
            y = np.array([1] * len(e1) + [0] * len(e2))
            pair_name = f"{f1}_vs_{f2}"
            result = run_probe(X, y, pair_name)
            fam_results[pair_name] = result

    report["tasks"]["tf_family_discrimination"] = {
        "species": "arabidopsis",
        "families_tested": list(family_embeddings.keys()),
        "n_per_family": {k: len(v) for k, v in family_embeddings.items()},
        "pairwise_results": fam_results,
    }

    # =========================================
    # Task 3: Cross-species embedding similarity
    # =========================================
    print("\n" + "=" * 60, flush=True)
    print("TASK 3: Cross-species TF embedding similarity", flush=True)

    # Pick well-known TFs present in multiple species
    test_tfs = ["MYB", "WRKY", "NAC", "ERF", "bHLH"]
    species_list = ["arabidopsis", "tomato", "rice", "human"]
    cross_species = {}

    for tf_prefix in test_tfs:
        tf_embs = {}
        for sp in species_list:
            genes = conn.execute(
                "SELECT symbol FROM genes WHERE species=? AND is_tf=1 AND symbol LIKE ? LIMIT 5",
                (sp, f"{tf_prefix}%")
            ).fetchall()
            embs = []
            for (symbol,) in genes:
                seq = fetch_protein_seq_uniprot(symbol, sp)
                if seq:
                    emb = extract_embedding(model, tokenizer, device, seq)
                    if emb is not None:
                        embs.append(emb)
                time.sleep(0.2)
            if embs:
                tf_embs[sp] = np.mean(embs, axis=0)
                print(f"  {tf_prefix}/{sp}: {len(embs)} seqs", flush=True)

        # Compute pairwise cosine similarities
        sps = list(tf_embs.keys())
        sims = {}
        for a in range(len(sps)):
            for b in range(a + 1, len(sps)):
                va, vb = tf_embs[sps[a]], tf_embs[sps[b]]
                cos = float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))
                sims[f"{sps[a]}_vs_{sps[b]}"] = round(cos, 4)
        cross_species[tf_prefix] = {"species_with_data": sps, "cosine_similarities": sims}

    report["tasks"]["cross_species_similarity"] = cross_species

    # Save
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n{'='*60}", flush=True)
    print(f"Results saved to {OUT}", flush=True)

    # Summary
    print("\nSUMMARY:", flush=True)
    for task_name, result in report["tasks"].items():
        if "best_cv_auc" in result:
            print(f"  {task_name}: CV-AUC={result['best_cv_auc']}", flush=True)
        elif "pairwise_results" in result:
            aucs = [r.get("best_cv_auc", 0) for r in result["pairwise_results"].values() if "best_cv_auc" in r]
            if aucs:
                print(f"  {task_name}: median pairwise AUC={np.median(aucs):.4f} ({len(aucs)} pairs)", flush=True)


if __name__ == "__main__":
    main()
