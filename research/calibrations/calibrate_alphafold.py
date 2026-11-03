#!/usr/bin/env python3
"""AlphaFold DB structural confidence calibration on GRN-Atlas data.

Tests what AlphaFold predicted structures reveal about our TF genes:
1. TF vs non-TF structural confidence (pLDDT) profiles
2. TF family structural distinctiveness
3. Cross-species structural conservation

Uses the AlphaFold DB REST API (pre-computed structures, no GPU needed).
Key metrics: globalMetricValue (mean pLDDT), fractionPlddtVeryHigh (>90),
fractionPlddtVeryLow (<50).

Usage:
  python backend/scripts/calibrate_alphafold.py > /tmp/alphafold_calibration.log 2>&1
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
OUT = Path(__file__).resolve().parents[1] / "data" / "alphafold_calibration.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import SPECIES_CONFIG

AF_API = "https://alphafold.ebi.ac.uk/api"


def get_uniprot_accession(gene_symbol: str, species: str) -> str | None:
    cfg = SPECIES_CONFIG.get(species, {})
    taxon = cfg.get("taxon_id")
    if not taxon:
        return None
    url = (f"https://rest.uniprot.org/uniprotkb/search?"
           f"query=gene:{gene_symbol}+AND+taxonomy_id:{taxon}+AND+reviewed:true"
           f"&format=json&size=1&fields=accession")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        if results:
            return results[0]["primaryAccession"]
    except Exception:
        pass

    # Fall back to unreviewed
    url2 = url.replace("+AND+reviewed:true", "")
    try:
        req = urllib.request.Request(url2, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        if results:
            return results[0]["primaryAccession"]
    except Exception:
        return None


def get_alphafold_prediction(uniprot_acc: str) -> dict | None:
    url = f"{AF_API}/prediction/{uniprot_acc}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, list) and data:
            return data[0]
        return None
    except Exception:
        return None


def get_plddt_per_residue(uniprot_acc: str, entry_id: str) -> list[float] | None:
    url = f"https://alphafold.ebi.ac.uk/files/{entry_id}-confidence_v6.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, list):
            return [r.get("confidenceScore", r.get("value", 0)) for r in data]
        elif isinstance(data, dict) and "confidenceScores" in data:
            return data["confidenceScores"]
        return None
    except Exception:
        return None


def collect_af_features(gene_symbol: str, species: str) -> dict | None:
    acc = get_uniprot_accession(gene_symbol, species)
    if not acc:
        return None
    time.sleep(0.2)

    pred = get_alphafold_prediction(acc)
    if not pred:
        return None
    time.sleep(0.2)

    features = {
        "symbol": gene_symbol,
        "species": species,
        "uniprot_acc": acc,
        "entry_id": pred.get("modelEntityId", pred.get("entryId", "")),
        "global_plddt": pred.get("globalMetricValue", 0),
        "frac_very_high": pred.get("fractionPlddtVeryHigh", 0),
        "frac_confident": pred.get("fractionPlddtConfident", 0),
        "frac_low": pred.get("fractionPlddtLow", 0),
        "frac_very_low": pred.get("fractionPlddtVeryLow", 0),
        "seq_length": pred.get("sequenceEnd", 0) - pred.get("sequenceStart", 0) + 1,
    }

    # Get per-residue pLDDT for more detailed analysis
    entry_id = features["entry_id"]
    if entry_id:
        plddt = get_plddt_per_residue(acc, entry_id)
        if plddt:
            features["plddt_std"] = round(float(np.std(plddt)), 2)
            features["plddt_min"] = round(float(np.min(plddt)), 2)
            features["plddt_max"] = round(float(np.max(plddt)), 2)
            # Fraction of disordered regions (pLDDT < 50)
            features["frac_disordered"] = round(sum(1 for p in plddt if p < 50) / len(plddt), 4)
            # Fraction of well-structured core (pLDDT > 90)
            features["frac_core"] = round(sum(1 for p in plddt if p > 90) / len(plddt), 4)
        time.sleep(0.2)

    return features


def run_probe(X, y, task_name: str) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    print(f"\n  Probe: {task_name} (n={len(y)}, pos={sum(y)}, neg={len(y)-sum(y)})", flush=True)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    results = {}
    for C in [0.01, 0.1, 1.0, 10.0]:
        clf = LogisticRegression(penalty="l1", C=C, solver="saga",
                                 max_iter=5000, random_state=42)
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        try:
            scores = cross_val_score(clf, X_scaled, y, cv=cv, scoring="roc_auc")
            mean_auc = round(float(scores.mean()), 4)
            std_auc = round(float(scores.std()), 4)
            results[str(C)] = {"cv_auc_mean": mean_auc, "cv_auc_std": std_auc}
            print(f"    C={C}: CV-AUC={mean_auc}±{std_auc}", flush=True)
        except Exception as e:
            print(f"    C={C}: error: {e}", flush=True)

    if results:
        best_C = max(results, key=lambda c: results[c]["cv_auc_mean"])
        best = results[best_C]
        print(f"    Best: C={best_C}, CV-AUC={best['cv_auc_mean']}", flush=True)
        return {"task": task_name, "best_C": float(best_C),
                "best_cv_auc": best["cv_auc_mean"], "probe_results": results}
    return {"task": task_name, "error": "no results"}


def main():
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA journal_mode=WAL")

    report = {
        "model": "AlphaFold DB (pre-computed structures)",
        "tasks": {},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # =========================================
    # Task 1: TF vs non-TF structural confidence
    # =========================================
    for species in ["arabidopsis", "human", "mouse"]:
        print(f"\n{'='*60}", flush=True)
        print(f"TASK 1: TF vs non-TF structural confidence ({species})", flush=True)

        tf_genes = conn.execute(
            "SELECT symbol FROM genes WHERE species=? AND is_tf=1 ORDER BY RANDOM() LIMIT 50",
            (species,)
        ).fetchall()
        nontf_genes = conn.execute(
            "SELECT symbol FROM genes WHERE species=? AND is_tf=0 ORDER BY RANDOM() LIMIT 50",
            (species,)
        ).fetchall()

        tf_features, nontf_features = [], []

        for (symbol,) in tf_genes:
            feat = collect_af_features(symbol, species)
            if feat and feat["global_plddt"] > 0:
                tf_features.append(feat)
                print(f"  TF {symbol}: pLDDT={feat['global_plddt']:.1f}, "
                      f"core={feat.get('frac_core', 'n/a')}", flush=True)

        for (symbol,) in nontf_genes:
            feat = collect_af_features(symbol, species)
            if feat and feat["global_plddt"] > 0:
                nontf_features.append(feat)
                print(f"  nonTF {symbol}: pLDDT={feat['global_plddt']:.1f}, "
                      f"core={feat.get('frac_core', 'n/a')}", flush=True)

        if len(tf_features) >= 10 and len(nontf_features) >= 10:
            # Build feature matrix
            feature_keys = ["global_plddt", "frac_very_high", "frac_confident",
                           "frac_low", "frac_very_low", "seq_length",
                           "plddt_std", "frac_disordered", "frac_core"]

            all_feats = tf_features + nontf_features
            X = []
            for f in all_feats:
                row = [f.get(k, 0) or 0 for k in feature_keys]
                X.append(row)
            X = np.array(X, dtype=float)
            y = np.array([1] * len(tf_features) + [0] * len(nontf_features))

            result = run_probe(X, y, f"tf_vs_nontf_{species}")
            result["n_tf"] = len(tf_features)
            result["n_nontf"] = len(nontf_features)
            result["features_used"] = feature_keys

            # Descriptive stats
            tf_plddt = [f["global_plddt"] for f in tf_features]
            nontf_plddt = [f["global_plddt"] for f in nontf_features]
            tf_core = [f.get("frac_core", 0) for f in tf_features]
            nontf_core = [f.get("frac_core", 0) for f in nontf_features]
            tf_len = [f["seq_length"] for f in tf_features]
            nontf_len = [f["seq_length"] for f in nontf_features]

            result["stats"] = {
                "tf_mean_plddt": round(float(np.mean(tf_plddt)), 1),
                "nontf_mean_plddt": round(float(np.mean(nontf_plddt)), 1),
                "tf_mean_core_frac": round(float(np.mean(tf_core)), 3),
                "nontf_mean_core_frac": round(float(np.mean(nontf_core)), 3),
                "tf_mean_length": round(float(np.mean(tf_len)), 0),
                "nontf_mean_length": round(float(np.mean(nontf_len)), 0),
            }
            print(f"\n  TF mean pLDDT: {np.mean(tf_plddt):.1f}, "
                  f"core: {np.mean(tf_core):.3f}, len: {np.mean(tf_len):.0f}", flush=True)
            print(f"  nonTF mean pLDDT: {np.mean(nontf_plddt):.1f}, "
                  f"core: {np.mean(nontf_core):.3f}, len: {np.mean(nontf_len):.0f}", flush=True)

            report["tasks"][f"tf_vs_nontf_{species}"] = result
        else:
            print(f"  Too few features: TF={len(tf_features)}, nonTF={len(nontf_features)}", flush=True)

    # =========================================
    # Task 2: TF family structural profiles
    # =========================================
    print(f"\n{'='*60}", flush=True)
    print("TASK 2: TF family structural profiles (arabidopsis)", flush=True)

    families = {"WRKY": "WRKY%", "MYB": "MYB%", "bHLH": "bHLH%",
                "ERF": "ERF%", "NAC": "NAC%", "bZIP": "bZIP%"}

    family_features = {}
    for fam_name, pattern in families.items():
        genes = conn.execute(
            "SELECT symbol FROM genes WHERE species='arabidopsis' AND is_tf=1 AND symbol LIKE ? ORDER BY RANDOM() LIMIT 15",
            (pattern,)
        ).fetchall()
        feats = []
        for (symbol,) in genes:
            feat = collect_af_features(symbol, "arabidopsis")
            if feat and feat["global_plddt"] > 0:
                feats.append(feat)
        if feats:
            family_features[fam_name] = feats
            mean_plddt = np.mean([f["global_plddt"] for f in feats])
            mean_core = np.mean([f.get("frac_core", 0) for f in feats])
            print(f"  {fam_name}: n={len(feats)}, pLDDT={mean_plddt:.1f}, "
                  f"core={mean_core:.3f}", flush=True)

    # Pairwise discrimination using structural features
    feature_keys = ["global_plddt", "frac_very_high", "frac_low", "frac_very_low",
                    "seq_length", "plddt_std", "frac_disordered", "frac_core"]

    fam_results = {}
    fam_names = list(family_features.keys())
    for i in range(len(fam_names)):
        for j in range(i + 1, len(fam_names)):
            f1, f2 = fam_names[i], fam_names[j]
            e1, e2 = family_features[f1], family_features[f2]
            if len(e1) < 5 or len(e2) < 5:
                continue
            all_f = e1 + e2
            X = np.array([[f.get(k, 0) or 0 for k in feature_keys] for f in all_f], dtype=float)
            y_arr = np.array([1] * len(e1) + [0] * len(e2))
            pair_name = f"{f1}_vs_{f2}"
            result = run_probe(X, y_arr, pair_name)
            fam_results[pair_name] = result

    report["tasks"]["tf_family_structure"] = {
        "species": "arabidopsis",
        "families": {k: {"n": len(v),
                         "mean_plddt": round(float(np.mean([f["global_plddt"] for f in v])), 1),
                         "mean_core": round(float(np.mean([f.get("frac_core", 0) for f in v])), 3)}
                     for k, v in family_features.items()},
        "pairwise_results": fam_results,
    }

    # Save
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n{'='*60}", flush=True)
    print(f"Results saved to {OUT}", flush=True)

    print("\nSUMMARY:", flush=True)
    for task_name, result in report["tasks"].items():
        if "best_cv_auc" in result:
            print(f"  {task_name}: CV-AUC={result['best_cv_auc']}", flush=True)
        elif "pairwise_results" in result:
            aucs = [r.get("best_cv_auc", 0) for r in result["pairwise_results"].values()
                    if "best_cv_auc" in r]
            if aucs:
                print(f"  {task_name}: median pairwise AUC={np.median(aucs):.4f}", flush=True)


if __name__ == "__main__":
    main()
