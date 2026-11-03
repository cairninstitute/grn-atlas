#!/usr/bin/env python3
"""Region classification battery for the Goodfire Evo2-7B SAE.

Tests whether the SAE can distinguish regulatory contexts that are useful
for the GRN Atlas: activated vs repressed promoters, binding sites vs
intergenic, and more.

Requires: PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

Tasks:
  1. Activator-target vs repressor-target promoters
  2. DAP-seq binding site vs random intergenic DNA
  3. Promoter vs intergenic DNA
  4. High-score vs low-score DAP-seq peaks
"""
from __future__ import annotations

import json
import os
import random
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
RESULTS_DIR = Path(__file__).resolve().parents[1] / "data"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnose_evo2_sae import (
    get_sae_features, _analyze_two_groups,
    fetch_ensembl_sequence, SPECIES_TAXONOMY,
)
from predict_structural_binding import ensure_tables


def fetch_ensembl_seq_cached(species_ensembl, chrom, start, end, strand=1):
    return fetch_ensembl_sequence(species_ensembl, chrom, start, end, strand)


# ---------------------------------------------------------------------------
# Task 1: Activator-target vs Repressor-target promoters
# ---------------------------------------------------------------------------

def task_activator_vs_repressor(conn, species: str, n: int):
    print("\n" + "=" * 60)
    print("TASK 1: Activator-target vs Repressor-target Promoters")
    print("=" * 60 + "\n")

    activator_rows = conn.execute("""
        SELECT DISTINCT p.gene_id, p.sequence, psc.mean_activation_score
        FROM perturbation_sign_consensus psc
        JOIN promoter_dna_sequences p ON p.gene_id = psc.target_id AND p.species = psc.species
        WHERE psc.species = ? AND psc.sign_consistency > 0.7
          AND psc.mean_activation_score > 0
          AND p.fetch_status = 'found' AND length(p.sequence) >= 150
        ORDER BY psc.sign_consistency DESC, psc.mean_activation_score DESC
        LIMIT ?
    """, (species, n)).fetchall()

    repressor_rows = conn.execute("""
        SELECT DISTINCT p.gene_id, p.sequence, psc.mean_activation_score
        FROM perturbation_sign_consensus psc
        JOIN promoter_dna_sequences p ON p.gene_id = psc.target_id AND p.species = psc.species
        WHERE psc.species = ? AND psc.sign_consistency > 0.7
          AND psc.mean_activation_score < 0
          AND p.fetch_status = 'found' AND length(p.sequence) >= 150
        ORDER BY psc.sign_consistency DESC, psc.mean_activation_score ASC
        LIMIT ?
    """, (species, n)).fetchall()

    print(f"Found {len(activator_rows)} activator-target promoters, "
          f"{len(repressor_rows)} repressor-target promoters with cached DNA", flush=True)

    act_vecs = []
    for gid, seq, score in activator_rows:
        print(f"  activator-target {gid[:15]}... score={score:.3f}", end=" ", flush=True)
        try:
            vec = get_sae_features(seq[:200], species)
            act_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)

    rep_vecs = []
    for gid, seq, score in repressor_rows:
        print(f"  repressor-target {gid[:15]}... score={score:.3f}", end=" ", flush=True)
        try:
            vec = get_sae_features(seq[:200], species)
            rep_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)

    if len(act_vecs) < 5 or len(rep_vecs) < 5:
        print("Not enough data", flush=True)
        return {"error": f"insufficient data: {len(act_vecs)} activator, {len(rep_vecs)} repressor"}

    return _analyze_two_groups(
        "activator_target", np.stack(act_vecs),
        "repressor_target", np.stack(rep_vecs),
    )


# ---------------------------------------------------------------------------
# Task 2: DAP-seq binding site vs random intergenic
# ---------------------------------------------------------------------------

def _get_intergenic_coords(conn, species: str, n: int, window: int = 200):
    gene_locs = conn.execute("""
        SELECT chromosome, start, end FROM gene_locations
        WHERE species = ? ORDER BY chromosome, start
    """, (species,)).fetchall()

    by_chrom = {}
    for chrom, s, e in gene_locs:
        by_chrom.setdefault(chrom, []).append((s, e))

    chroms = conn.execute("""
        SELECT DISTINCT chromosome FROM gene_locations
        WHERE species = ? ORDER BY chromosome
    """, (species,)).fetchall()

    chrom_maxes = {}
    for (chrom,) in chroms:
        mx = max(e for c, s, e in gene_locs if c == chrom)
        chrom_maxes[chrom] = mx

    coords = []
    attempts = 0
    while len(coords) < n and attempts < n * 20:
        attempts += 1
        chrom = random.choice(list(chrom_maxes.keys()))
        max_pos = chrom_maxes[chrom]
        if max_pos < window + 1000:
            continue
        pos = random.randint(1000, max_pos - window)

        gene_list = by_chrom.get(chrom, [])
        too_close = False
        for gs, ge in gene_list:
            if pos < ge + 2000 and pos + window > gs - 2000:
                too_close = True
                break
        if not too_close:
            coords.append((chrom, pos, pos + window))

    return coords


def task_binding_vs_intergenic(conn, species: str, n: int):
    print("\n" + "=" * 60)
    print("TASK 2: DAP-seq Binding Site vs Random Intergenic")
    print("=" * 60 + "\n")

    species_ensembl = {"arabidopsis": "arabidopsis_thaliana", "human": "homo_sapiens"}
    ens_sp = species_ensembl.get(species)
    if not ens_sp:
        return {"error": f"no ensembl mapping for {species}"}

    chrom_map = {"Chr1": "1", "Chr2": "2", "Chr3": "3", "Chr4": "4", "Chr5": "5",
                 "ChrC": "Pt", "ChrM": "Mt"}

    peak_rows = conn.execute("""
        SELECT DISTINCT chrom, summit - 100, summit + 100, score
        FROM chromatin_peaks
        WHERE species = ? AND peak_type = 'DAP-seq' AND score >= 200 AND summit IS NOT NULL
        ORDER BY RANDOM()
        LIMIT ?
    """, (species, n * 3)).fetchall()

    print(f"Scoring {min(n, len(peak_rows))} DAP-seq binding sites...", flush=True)
    binding_vecs = []
    for chrom, start, end, score in peak_rows:
        if len(binding_vecs) >= n:
            break
        ens_chrom = chrom_map.get(chrom, chrom)
        seq = fetch_ensembl_seq_cached(ens_sp, ens_chrom, max(1, start), end)
        if not seq or len(seq) < 150:
            continue
        print(f"  binding {chrom}:{start}-{end} score={score:.0f}...", end=" ", flush=True)
        try:
            vec = get_sae_features(seq[:200], species)
            binding_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)
        time.sleep(0.1)

    print(f"\nScoring {n} random intergenic regions...", flush=True)
    intergenic_coords = _get_intergenic_coords(conn, species, n * 3)
    intergenic_vecs = []
    for chrom, start, end in intergenic_coords:
        if len(intergenic_vecs) >= n:
            break
        ens_chrom = chrom_map.get(chrom, chrom)
        seq = fetch_ensembl_seq_cached(ens_sp, ens_chrom, start, end)
        if not seq or len(seq) < 150:
            continue
        print(f"  intergenic {chrom}:{start}-{end}...", end=" ", flush=True)
        try:
            vec = get_sae_features(seq[:200], species)
            intergenic_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)
        time.sleep(0.1)

    if len(binding_vecs) < 5 or len(intergenic_vecs) < 5:
        return {"error": f"insufficient data: {len(binding_vecs)} binding, {len(intergenic_vecs)} intergenic"}

    return _analyze_two_groups(
        "dap_binding", np.stack(binding_vecs),
        "intergenic", np.stack(intergenic_vecs),
    )


# ---------------------------------------------------------------------------
# Task 3: Promoter vs Intergenic
# ---------------------------------------------------------------------------

def task_promoter_vs_intergenic(conn, species: str, n: int):
    print("\n" + "=" * 60)
    print("TASK 3: Promoter vs Intergenic DNA")
    print("=" * 60 + "\n")

    species_ensembl = {"arabidopsis": "arabidopsis_thaliana", "human": "homo_sapiens"}
    ens_sp = species_ensembl.get(species)
    if not ens_sp:
        return {"error": f"no ensembl mapping for {species}"}

    chrom_map = {"Chr1": "1", "Chr2": "2", "Chr3": "3", "Chr4": "4", "Chr5": "5",
                 "ChrC": "Pt", "ChrM": "Mt"}

    promoter_rows = conn.execute("""
        SELECT p.gene_id, p.sequence
        FROM promoter_dna_sequences p
        WHERE p.species = ? AND p.fetch_status = 'found' AND length(p.sequence) >= 150
        ORDER BY RANDOM() LIMIT ?
    """, (species, n)).fetchall()

    print(f"Scoring {len(promoter_rows)} promoters...", flush=True)
    promoter_vecs = []
    for gid, seq in promoter_rows:
        print(f"  promoter {gid[:15]}...", end=" ", flush=True)
        try:
            vec = get_sae_features(seq[:200], species)
            promoter_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)

    print(f"\nScoring {n} random intergenic regions...", flush=True)
    intergenic_coords = _get_intergenic_coords(conn, species, n * 3)
    intergenic_vecs = []
    for chrom, start, end in intergenic_coords:
        if len(intergenic_vecs) >= n:
            break
        ens_chrom = chrom_map.get(chrom, chrom)
        seq = fetch_ensembl_seq_cached(ens_sp, ens_chrom, start, end)
        if not seq or len(seq) < 150:
            continue
        print(f"  intergenic {chrom}:{start}-{end}...", end=" ", flush=True)
        try:
            vec = get_sae_features(seq[:200], species)
            intergenic_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)
        time.sleep(0.1)

    if len(promoter_vecs) < 5 or len(intergenic_vecs) < 5:
        return {"error": f"insufficient data: {len(promoter_vecs)} promoter, {len(intergenic_vecs)} intergenic"}

    return _analyze_two_groups(
        "promoter", np.stack(promoter_vecs),
        "intergenic", np.stack(intergenic_vecs),
    )


# ---------------------------------------------------------------------------
# Task 4: High-score vs low-score DAP-seq peaks
# ---------------------------------------------------------------------------

def task_peak_quality(conn, species: str, n: int):
    print("\n" + "=" * 60)
    print("TASK 4: High-score vs Low-score DAP-seq Peaks")
    print("=" * 60 + "\n")

    species_ensembl = {"arabidopsis": "arabidopsis_thaliana", "human": "homo_sapiens"}
    ens_sp = species_ensembl.get(species)
    if not ens_sp:
        return {"error": f"no ensembl mapping for {species}"}

    chrom_map = {"Chr1": "1", "Chr2": "2", "Chr3": "3", "Chr4": "4", "Chr5": "5",
                 "ChrC": "Pt", "ChrM": "Mt"}

    high_rows = conn.execute("""
        SELECT DISTINCT chrom, summit - 100, summit + 100, score
        FROM chromatin_peaks
        WHERE species = ? AND peak_type = 'DAP-seq' AND score >= 500 AND summit IS NOT NULL
        ORDER BY RANDOM() LIMIT ?
    """, (species, n * 3)).fetchall()

    low_rows = conn.execute("""
        SELECT DISTINCT chrom, summit - 100, summit + 100, score
        FROM chromatin_peaks
        WHERE species = ? AND peak_type = 'DAP-seq' AND score > 0 AND score < 100 AND summit IS NOT NULL
        ORDER BY RANDOM() LIMIT ?
    """, (species, n * 3)).fetchall()

    print(f"Scoring high-confidence peaks (score>=500)...", flush=True)
    high_vecs = []
    for chrom, start, end, score in high_rows:
        if len(high_vecs) >= n:
            break
        ens_chrom = chrom_map.get(chrom, chrom)
        seq = fetch_ensembl_seq_cached(ens_sp, ens_chrom, max(1, start), end)
        if not seq or len(seq) < 150:
            continue
        print(f"  high {chrom}:{start}-{end} score={score:.0f}...", end=" ", flush=True)
        try:
            vec = get_sae_features(seq[:200], species)
            high_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)
        time.sleep(0.1)

    print(f"\nScoring low-confidence peaks (score<100)...", flush=True)
    low_vecs = []
    for chrom, start, end, score in low_rows:
        if len(low_vecs) >= n:
            break
        ens_chrom = chrom_map.get(chrom, chrom)
        seq = fetch_ensembl_seq_cached(ens_sp, ens_chrom, max(1, start), end)
        if not seq or len(seq) < 150:
            continue
        print(f"  low {chrom}:{start}-{end} score={score:.0f}...", end=" ", flush=True)
        try:
            vec = get_sae_features(seq[:200], species)
            low_vecs.append(vec)
            print(f"active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"error: {e}", flush=True)
        time.sleep(0.1)

    if len(high_vecs) < 5 or len(low_vecs) < 5:
        return {"error": f"insufficient data: {len(high_vecs)} high, {len(low_vecs)} low"}

    return _analyze_two_groups(
        "high_peak", np.stack(high_vecs),
        "low_peak", np.stack(low_vecs),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Region classification via Evo2 SAE")
    parser.add_argument("--task", default="all",
                        choices=["all", "activator_vs_repressor", "binding_vs_intergenic",
                                 "promoter_vs_intergenic", "peak_quality"])
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default="arabidopsis")
    parser.add_argument("--n-samples", type=int, default=20)
    args = parser.parse_args()

    random.seed(42)

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_tables(conn)

    all_results = {}
    tasks = {
        "activator_vs_repressor": lambda: task_activator_vs_repressor(conn, args.species, args.n_samples),
        "binding_vs_intergenic": lambda: task_binding_vs_intergenic(conn, args.species, args.n_samples),
        "promoter_vs_intergenic": lambda: task_promoter_vs_intergenic(conn, args.species, args.n_samples),
        "peak_quality": lambda: task_peak_quality(conn, args.species, args.n_samples),
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

    out = RESULTS_DIR / "evo2_sae_region_classification.json"
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
        else:
            print(f"  {name}: completed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
