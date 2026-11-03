#!/usr/bin/env python3
"""Large-scale SAE validation across 5 species and multiple region types.

Designed to run fully autonomously without Claude tokens.
Uses local Evo2-7B + Goodfire SAE (layer 26) on GPU.
Fetches sequences from Ensembl REST with rate limiting.

Species tested: arabidopsis, human, mouse, rice, potato
Tasks per species:
  A. Promoter vs coding DNA
  B. Promoter vs intergenic DNA
  C. Species-pair discrimination (all 10 pairs)
  D. Activator vs repressor target promoters (arabidopsis, human, mouse only)

Ensembl rate limit: 15 req/s, we use 0.1s delay = ~10 req/s.
GPU inference: ~2-3 sec/sequence on RTX 5070 Ti.

Usage:
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python3 validate_sae_large_scale.py

Results saved to: backend/data/evo2_sae_large_validation.json
Progress log: prints to stdout, pipe to file for monitoring.
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
from itertools import combinations
from pathlib import Path

import numpy as np

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
RESULTS_DIR = Path(__file__).resolve().parents[1] / "data"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MAX_PROMOTERS_PER_SPECIES = 100
MAX_CODING_PER_SPECIES = 100
MAX_INTERGENIC_PER_SPECIES = 100
MAX_SIGNED_PER_CLASS = 50
DNA_WINDOW = 200
ENSEMBL_DELAY = 0.12  # seconds between Ensembl requests (~8 req/s, safe margin)

SPECIES_CONFIG = {
    "arabidopsis": {
        "ensembl": "arabidopsis_thaliana",
        "taxonomy": "|D__Viridiplantae;P__Streptophyta;C__Magnoliopsida;O__Brassicales;F__Brassicaceae;G__Arabidopsis;S__Arabidopsis thaliana|",
        "chromosomes": ["1", "2", "3", "4", "5"],
        "has_signed_edges": True,
        "has_dap_seq": True,
    },
    "human": {
        "ensembl": "homo_sapiens",
        "taxonomy": "|D__Metazoa;P__Chordata;C__Mammalia;O__Primates;F__Hominidae;G__Homo;S__Homo sapiens|",
        "chromosomes": [str(i) for i in range(1, 23)] + ["X"],
        "has_signed_edges": True,
        "has_dap_seq": False,
    },
    "mouse": {
        "ensembl": "mus_musculus",
        "taxonomy": "|D__Metazoa;P__Chordata;C__Mammalia;O__Rodentia;F__Muridae;G__Mus;S__Mus musculus|",
        "chromosomes": [str(i) for i in range(1, 20)] + ["X"],
        "has_signed_edges": True,
        "has_dap_seq": False,
    },
    "rice": {
        "ensembl": "oryza_sativa",
        "taxonomy": "|D__Viridiplantae;P__Streptophyta;C__Liliopsida;O__Poales;F__Poaceae;G__Oryza;S__Oryza sativa|",
        "chromosomes": [str(i) for i in range(1, 13)],
        "has_signed_edges": False,
        "has_dap_seq": False,
    },
    "potato": {
        "ensembl": "solanum_tuberosum",
        "taxonomy": "|D__Viridiplantae;P__Streptophyta;C__Magnoliopsida;O__Solanales;F__Solanaceae;G__Solanum;S__Solanum tuberosum|",
        "chromosomes": [str(i) for i in range(1, 13)],
        "has_signed_edges": False,
        "has_dap_seq": False,
    },
}

# DB chromosome names → Ensembl chromosome names
CHROM_TO_ENSEMBL = {
    "potato": {f"ST4.03ch{i:02d}": str(i) for i in range(13)},
}


def _ensembl_chrom(species: str, db_chrom: str) -> str:
    """Map a DB chromosome name to the Ensembl equivalent."""
    mapping = CHROM_TO_ENSEMBL.get(species)
    if mapping:
        return mapping.get(db_chrom, db_chrom)
    return db_chrom


# ---------------------------------------------------------------------------
# Ensembl sequence fetching with caching and rate limiting
# ---------------------------------------------------------------------------

_ensembl_cache: dict[str, str | None] = {}
_last_ensembl_request = 0.0


def fetch_ensembl_sequence(ensembl_species: str, chrom: str, start: int,
                           end: int, strand: int = 1) -> str | None:
    global _last_ensembl_request
    cache_key = f"{ensembl_species}:{chrom}:{start}:{end}:{strand}"
    if cache_key in _ensembl_cache:
        return _ensembl_cache[cache_key]

    elapsed = time.time() - _last_ensembl_request
    if elapsed < ENSEMBL_DELAY:
        time.sleep(ENSEMBL_DELAY - elapsed)

    url = (f"https://rest.ensembl.org/sequence/region/{ensembl_species}/"
           f"{chrom}:{start}..{end}:{strand}?content-type=text/plain")

    for attempt in range(3):
        try:
            _last_ensembl_request = time.time()
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                seq = resp.read().decode().strip()
            if set(seq.upper()) <= {"A", "C", "G", "T", "N"}:
                _ensembl_cache[cache_key] = seq
                return seq
            _ensembl_cache[cache_key] = None
            return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(30, 2 ** (attempt + 1))
                print(f"    Rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            _ensembl_cache[cache_key] = None
            return None
        except Exception:
            if attempt < 2:
                time.sleep(1)
                continue
            _ensembl_cache[cache_key] = None
            return None




# ---------------------------------------------------------------------------
# SAE feature extraction (reuses diagnose_evo2_sae infrastructure)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parent))

_evo2 = None
_sae = None
_tax_cache = {}

SAE_REPO = "Goodfire/Evo-2-Layer-26-Mixed"
SAE_FILE = "sae-layer26-mixed-expansion_8-k_64.pt"


def get_evo2():
    global _evo2
    if _evo2 is None:
        import torch
        from evo2 import Evo2
        print("[MODEL] Loading Evo2-7B...", flush=True)
        _evo2 = Evo2("evo2_7b")
        print("[MODEL] Evo2-7B loaded.", flush=True)
    return _evo2


def get_sae():
    global _sae
    if _sae is None:
        import torch
        from huggingface_hub import hf_hub_download
        print("[MODEL] Loading SAE...", flush=True)
        path = hf_hub_download(repo_id=SAE_REPO, filename=SAE_FILE, repo_type="model")
        state = torch.load(path, map_location="cpu", weights_only=True)
        clean = {k.replace("_orig_mod.", "").replace("module.", ""): v
                 for k, v in state.items()}

        from diagnose_evo2_sae import BatchTopKTiedSAE
        _sae = BatchTopKTiedSAE(4096, 32768, 64)
        _sae.load_state_dict(clean)
        _sae.eval()
        print("[MODEL] SAE loaded.", flush=True)
    return _sae


def _tax_len(species: str) -> int:
    if species not in _tax_cache:
        taxonomy = SPECIES_CONFIG[species]["taxonomy"]
        evo2 = get_evo2()
        _tax_cache[species] = len(evo2.tokenizer.tokenize(taxonomy))
    return _tax_cache[species]


def get_sae_features(dna_seq: str, species: str) -> np.ndarray:
    """Mean-pooled SAE features (32768,) for a DNA sequence."""
    import torch
    evo2 = get_evo2()
    sae = get_sae()
    taxonomy = SPECIES_CONFIG[species]["taxonomy"]
    sequence = taxonomy + dna_seq

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

    return sae_feats.mean(axis=0)


# ---------------------------------------------------------------------------
# Sequence collection per species
# ---------------------------------------------------------------------------

def collect_promoter_seqs(conn, species: str, n: int) -> list[tuple[str, np.ndarray]]:
    """Collect promoter sequences: use cache first, then fetch from Ensembl."""
    cfg = SPECIES_CONFIG[species]

    # First: use cached promoter DNA
    cached = conn.execute("""
        SELECT p.gene_id, p.sequence
        FROM promoter_dna_sequences p
        WHERE p.species = ? AND p.fetch_status = 'found' AND length(p.sequence) >= ?
        ORDER BY RANDOM()
    """, (species, DNA_WINDOW - 50)).fetchall()

    results = []
    for gid, seq in cached:
        if len(results) >= n:
            break
        seq = seq[:DNA_WINDOW]
        try:
            vec = get_sae_features(seq, species)
            results.append((gid, vec))
            print(f"    promoter {gid[:20]} [cached] active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"    promoter {gid[:20]} error: {e}", flush=True)

    if len(results) >= n:
        return results

    # Fetch more from Ensembl
    genes = conn.execute("""
        SELECT g.id, gl.chromosome, gl.start, gl.end, gl.strand
        FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id AND gl.species = g.species
        WHERE g.species = ?
        ORDER BY RANDOM()
    """, (species,)).fetchall()

    cached_ids = {r[0] for r in results}
    for gid, chrom, start, end, strand in genes:
        if len(results) >= n:
            break
        if gid in cached_ids:
            continue

        # Compute promoter window: -150 to +50 from TSS
        if strand >= 0:
            tss = start
            p_start = max(1, tss - 150)
            p_end = tss + 50
        else:
            tss = end
            p_start = max(1, tss - 50)
            p_end = tss + 150

        ens_chrom = _ensembl_chrom(species, str(chrom))
        seq = fetch_ensembl_sequence(cfg["ensembl"], ens_chrom, p_start, p_end, 1 if strand >= 0 else -1)
        if not seq or len(seq) < DNA_WINDOW - 50:
            continue

        seq = seq[:DNA_WINDOW]
        try:
            vec = get_sae_features(seq, species)
            results.append((gid, vec))
            print(f"    promoter {gid[:20]} [ensembl] active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"    promoter {gid[:20]} error: {e}", flush=True)

    return results


def collect_coding_seqs(conn, species: str, n: int) -> list[tuple[str, np.ndarray]]:
    """Collect gene-body DNA (first 200bp past TSS) as coding-region proxy.

    Uses genomic coordinates from gene_locations — works for all species
    without needing Ensembl gene IDs for CDS lookup.
    """
    cfg = SPECIES_CONFIG[species]

    genes = conn.execute("""
        SELECT g.id, g.symbol, gl.chromosome, gl.start, gl.end, gl.strand
        FROM genes g
        JOIN gene_locations gl ON gl.gene_id = g.id AND gl.species = g.species
        WHERE g.species = ? AND (gl.end - gl.start) > ?
        ORDER BY RANDOM()
    """, (species, DNA_WINDOW + 100)).fetchall()

    results = []
    for gid, sym, chrom, start, end, strand in genes:
        if len(results) >= n:
            break

        # Gene body: first 200bp past TSS (inside the transcribed region)
        if strand >= 0:
            gb_start = start + 100  # skip 5'UTR region
            gb_end = gb_start + DNA_WINDOW
        else:
            gb_end = end - 100
            gb_start = gb_end - DNA_WINDOW

        if gb_start < 1 or gb_end <= gb_start:
            continue

        ens_chrom = _ensembl_chrom(species, str(chrom))
        seq = fetch_ensembl_sequence(cfg["ensembl"], ens_chrom, gb_start, gb_end,
                                     1 if strand >= 0 else -1)
        if not seq or len(seq) < DNA_WINDOW - 50 or "N" * 20 in seq.upper():
            continue

        seq = seq[:DNA_WINDOW]
        try:
            vec = get_sae_features(seq, species)
            results.append((gid, vec))
            print(f"    coding {(sym or gid)[:20]} active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"    coding {(sym or gid)[:20]} error: {e}", flush=True)

    return results


def collect_intergenic_seqs(conn, species: str, n: int) -> list[tuple[str, np.ndarray]]:
    """Collect random intergenic sequences from Ensembl."""
    cfg = SPECIES_CONFIG[species]

    gene_locs = conn.execute("""
        SELECT chromosome, start, end FROM gene_locations WHERE species = ?
    """, (species,)).fetchall()

    by_chrom: dict[str, list[tuple[int, int]]] = {}
    chrom_maxes: dict[str, int] = {}
    for chrom, s, e in gene_locs:
        db_chrom = str(chrom)
        by_chrom.setdefault(db_chrom, []).append((s, e))
        chrom_maxes[db_chrom] = max(chrom_maxes.get(db_chrom, 0), e)

    valid_chroms = list(chrom_maxes.keys())

    results = []
    attempts = 0
    while len(results) < n and attempts < n * 30:
        attempts += 1
        db_chrom = random.choice(valid_chroms)
        max_pos = chrom_maxes.get(db_chrom, 0)
        if max_pos < DNA_WINDOW + 5000:
            continue
        pos = random.randint(2000, max_pos - DNA_WINDOW - 2000)

        gene_list = by_chrom.get(db_chrom, [])
        too_close = any(pos < ge + 2000 and pos + DNA_WINDOW > gs - 2000
                        for gs, ge in gene_list)
        if too_close:
            continue

        ens_chrom = _ensembl_chrom(species, db_chrom)
        seq = fetch_ensembl_sequence(cfg["ensembl"], ens_chrom, pos, pos + DNA_WINDOW)
        if not seq or len(seq) < DNA_WINDOW - 50 or "N" * 20 in seq.upper():
            continue

        seq = seq[:DNA_WINDOW]
        try:
            vec = get_sae_features(seq, species)
            results.append((f"{db_chrom}:{pos}", vec))
            print(f"    intergenic {db_chrom}:{pos} active={(vec > 0).sum()}", flush=True)
        except Exception as e:
            print(f"    intergenic {db_chrom}:{pos} error: {e}", flush=True)

    return results


def collect_signed_promoters(conn, species: str, sign: str, n: int) -> list[tuple[str, np.ndarray]]:
    """Collect promoter sequences for activator or repressor targets."""
    if sign == "activator":
        condition = "psc.mean_activation_score > 0"
        order = "psc.mean_activation_score DESC"
    else:
        condition = "psc.mean_activation_score < 0"
        order = "psc.mean_activation_score ASC"

    cfg = SPECIES_CONFIG[species]

    # First try cached
    rows = conn.execute(f"""
        SELECT DISTINCT psc.target_id, p.sequence, psc.mean_activation_score
        FROM perturbation_sign_consensus psc
        JOIN promoter_dna_sequences p ON p.gene_id = psc.target_id AND p.species = psc.species
        WHERE psc.species = ? AND psc.sign_consistency > 0.7
          AND {condition}
          AND p.fetch_status = 'found' AND length(p.sequence) >= ?
        ORDER BY psc.sign_consistency DESC, {order}
    """, (species, DNA_WINDOW - 50)).fetchall()

    results = []
    for gid, seq, score in rows:
        if len(results) >= n:
            break
        seq = seq[:DNA_WINDOW]
        try:
            vec = get_sae_features(seq, species)
            results.append((gid, vec))
            print(f"    {sign} {gid[:20]} [cached] score={score:.3f} active={(vec > 0).sum()}",
                  flush=True)
        except Exception as e:
            print(f"    {sign} {gid[:20]} error: {e}", flush=True)

    if len(results) >= n:
        return results

    # Fetch more from Ensembl
    more_rows = conn.execute(f"""
        SELECT DISTINCT psc.target_id, gl.chromosome, gl.start, gl.end, gl.strand,
               psc.mean_activation_score
        FROM perturbation_sign_consensus psc
        JOIN gene_locations gl ON gl.gene_id = psc.target_id AND gl.species = psc.species
        WHERE psc.species = ? AND psc.sign_consistency > 0.7 AND {condition}
        ORDER BY psc.sign_consistency DESC, {order}
    """, (species,)).fetchall()

    cached_ids = {r[0] for r in results}
    for gid, chrom, start, end, strand, score in more_rows:
        if len(results) >= n:
            break
        if gid in cached_ids:
            continue

        if strand >= 0:
            tss = start
            p_start = max(1, tss - 150)
            p_end = tss + 50
        else:
            tss = end
            p_start = max(1, tss - 50)
            p_end = tss + 150

        ens_chrom = _ensembl_chrom(species, str(chrom))
        seq = fetch_ensembl_sequence(cfg["ensembl"], ens_chrom, p_start, p_end,
                                     1 if strand >= 0 else -1)
        if not seq or len(seq) < DNA_WINDOW - 50:
            continue

        seq = seq[:DNA_WINDOW]
        try:
            vec = get_sae_features(seq, species)
            results.append((gid, vec))
            print(f"    {sign} {gid[:20]} [ensembl] score={score:.3f} active={(vec > 0).sum()}",
                  flush=True)
        except Exception as e:
            print(f"    {sign} {gid[:20]} error: {e}", flush=True)

    return results


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_two_groups(name_a: str, vecs_a: list, name_b: str, vecs_b: list) -> dict:
    """Cohen's d analysis + C-sweep logistic regression probe."""
    mat_a = np.stack([v for _, v in vecs_a])
    mat_b = np.stack([v for _, v in vecs_b])

    a_mean = mat_a.mean(axis=0)
    b_mean = mat_b.mean(axis=0)
    pooled_std = np.sqrt((mat_a.std(axis=0)**2 + mat_b.std(axis=0)**2) / 2 + 1e-10)
    cohens_d = (a_mean - b_mean) / pooled_std

    n_large = int((np.abs(cohens_d) > 0.8).sum())
    n_medium = int(((np.abs(cohens_d) > 0.5) & (np.abs(cohens_d) <= 0.8)).sum())

    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    X = np.vstack([mat_a, mat_b])
    y = np.array([0] * len(mat_a) + [1] * len(mat_b))
    n_splits = min(5, min(len(mat_a), len(mat_b)))

    best_auc, best_C = None, None
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
            auc_results[str(C)] = round(float(aucs.mean()), 4)
            if best_auc is None or aucs.mean() > best_auc:
                best_auc = float(aucs.mean())
                best_C = C

    verdict = ("STRONG" if (best_auc and best_auc > 0.75) else
               "MODERATE" if (best_auc and best_auc > 0.65) else
               "WEAK" if (best_auc and best_auc > 0.55) else "NONE")

    top_a_idx = np.argsort(cohens_d)[-5:][::-1]
    top_b_idx = np.argsort(cohens_d)[:5]

    print(f"  RESULT: {name_a} vs {name_b}: n={len(mat_a)}+{len(mat_b)}, "
          f"AUC={best_auc:.3f}, |d|>0.8: {n_large}, verdict: {verdict}", flush=True)
    print(f"  C sweep: {auc_results}", flush=True)

    return {
        f"n_{name_a}": len(mat_a),
        f"n_{name_b}": len(mat_b),
        "probe_auc": round(best_auc, 4) if best_auc else None,
        "best_C": best_C,
        "c_sweep": auc_results,
        "verdict": verdict,
        "features_large_d": n_large,
        "features_medium_d": n_medium,
        f"top_{name_a}": [{"f": int(f), "d": round(float(cohens_d[f]), 4)} for f in top_a_idx],
        f"top_{name_b}": [{"f": int(f), "d": round(float(cohens_d[f]), 4)} for f in top_b_idx],
    }


# ---------------------------------------------------------------------------
# Main validation pipeline
# ---------------------------------------------------------------------------

def main():
    random.seed(42)
    np.random.seed(42)

    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA journal_mode=WAL")

    results = {
        "validation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "max_promoters": MAX_PROMOTERS_PER_SPECIES,
            "max_coding": MAX_CODING_PER_SPECIES,
            "max_intergenic": MAX_INTERGENIC_PER_SPECIES,
            "max_signed_per_class": MAX_SIGNED_PER_CLASS,
            "dna_window": DNA_WINDOW,
            "species": list(SPECIES_CONFIG.keys()),
        },
        "per_species": {},
        "cross_species": {},
        "signed_edges": {},
    }

    # ------------------------------------------------------------------
    # Phase 1: Collect all sequences per species
    # ------------------------------------------------------------------
    all_promoters: dict[str, list] = {}
    all_coding: dict[str, list] = {}
    all_intergenic: dict[str, list] = {}

    for species in SPECIES_CONFIG:
        print(f"\n{'='*60}", flush=True)
        print(f"COLLECTING SEQUENCES: {species}", flush=True)
        print(f"{'='*60}", flush=True)

        print(f"\n  [1/{species}] Collecting promoters (max {MAX_PROMOTERS_PER_SPECIES})...",
              flush=True)
        all_promoters[species] = collect_promoter_seqs(conn, species, MAX_PROMOTERS_PER_SPECIES)
        print(f"  Collected {len(all_promoters[species])} promoters", flush=True)

        print(f"\n  [2/{species}] Collecting coding sequences (max {MAX_CODING_PER_SPECIES})...",
              flush=True)
        all_coding[species] = collect_coding_seqs(conn, species, MAX_CODING_PER_SPECIES)
        print(f"  Collected {len(all_coding[species])} coding", flush=True)

        print(f"\n  [3/{species}] Collecting intergenic sequences (max {MAX_INTERGENIC_PER_SPECIES})...",
              flush=True)
        all_intergenic[species] = collect_intergenic_seqs(conn, species, MAX_INTERGENIC_PER_SPECIES)
        print(f"  Collected {len(all_intergenic[species])} intergenic", flush=True)

    # ------------------------------------------------------------------
    # Phase 2: Per-species region classification
    # ------------------------------------------------------------------
    for species in SPECIES_CONFIG:
        print(f"\n{'='*60}", flush=True)
        print(f"ANALYSIS: {species}", flush=True)
        print(f"{'='*60}", flush=True)

        sp_results = {}

        # A. Promoter vs coding
        p = all_promoters[species]
        c = all_coding[species]
        if len(p) >= 5 and len(c) >= 5:
            print(f"\n  Task A: Promoter vs Coding ({len(p)} vs {len(c)})", flush=True)
            sp_results["promoter_vs_coding"] = analyze_two_groups("promoter", p, "coding", c)
        else:
            sp_results["promoter_vs_coding"] = {
                "error": f"insufficient data: {len(p)} promoter, {len(c)} coding"
            }
            print(f"\n  Task A: SKIPPED (insufficient data)", flush=True)

        # B. Promoter vs intergenic
        ig = all_intergenic[species]
        if len(p) >= 5 and len(ig) >= 5:
            print(f"\n  Task B: Promoter vs Intergenic ({len(p)} vs {len(ig)})", flush=True)
            sp_results["promoter_vs_intergenic"] = analyze_two_groups("promoter", p, "intergenic", ig)
        else:
            sp_results["promoter_vs_intergenic"] = {
                "error": f"insufficient data: {len(p)} promoter, {len(ig)} intergenic"
            }
            print(f"\n  Task B: SKIPPED (insufficient data)", flush=True)

        results["per_species"][species] = sp_results

        # Save intermediate results after each species
        out = RESULTS_DIR / "evo2_sae_large_validation.json"
        out.write_text(json.dumps(results, indent=2, default=str))

    # ------------------------------------------------------------------
    # Phase 3: Cross-species discrimination (all pairs)
    # ------------------------------------------------------------------
    print(f"\n{'='*60}", flush=True)
    print(f"CROSS-SPECIES DISCRIMINATION", flush=True)
    print(f"{'='*60}", flush=True)

    species_list = [s for s in SPECIES_CONFIG if len(all_promoters.get(s, [])) >= 5]
    for sp_a, sp_b in combinations(species_list, 2):
        pa = all_promoters[sp_a]
        pb = all_promoters[sp_b]
        n_use = min(len(pa), len(pb), 50)
        if n_use < 5:
            results["cross_species"][f"{sp_a}_vs_{sp_b}"] = {"error": "insufficient data"}
            continue

        pa_sub = random.sample(pa, n_use)
        pb_sub = random.sample(pb, n_use)

        print(f"\n  {sp_a} vs {sp_b} ({n_use} vs {n_use} promoters)", flush=True)
        results["cross_species"][f"{sp_a}_vs_{sp_b}"] = analyze_two_groups(
            sp_a, pa_sub, sp_b, pb_sub
        )

    # Save intermediate
    out = RESULTS_DIR / "evo2_sae_large_validation.json"
    out.write_text(json.dumps(results, indent=2, default=str))

    # ------------------------------------------------------------------
    # Phase 4: Activator vs repressor (species with signed edges)
    # ------------------------------------------------------------------
    print(f"\n{'='*60}", flush=True)
    print(f"ACTIVATOR vs REPRESSOR TARGETS", flush=True)
    print(f"{'='*60}", flush=True)

    for species in SPECIES_CONFIG:
        if not SPECIES_CONFIG[species]["has_signed_edges"]:
            continue

        print(f"\n  {species}: collecting signed promoters...", flush=True)
        act = collect_signed_promoters(conn, species, "activator", MAX_SIGNED_PER_CLASS)
        rep = collect_signed_promoters(conn, species, "repressor", MAX_SIGNED_PER_CLASS)

        if len(act) >= 5 and len(rep) >= 5:
            print(f"  {species}: {len(act)} activator, {len(rep)} repressor", flush=True)
            results["signed_edges"][species] = analyze_two_groups(
                "activator_target", act, "repressor_target", rep
            )
        else:
            results["signed_edges"][species] = {
                "error": f"insufficient data: {len(act)} activator, {len(rep)} repressor"
            }
            print(f"  {species}: SKIPPED (insufficient data)", flush=True)

    # ------------------------------------------------------------------
    # Final save
    # ------------------------------------------------------------------
    conn.close()

    out = RESULTS_DIR / "evo2_sae_large_validation.json"
    out.write_text(json.dumps(results, indent=2, default=str))

    # Print summary
    print(f"\n{'='*60}", flush=True)
    print(f"VALIDATION COMPLETE", flush=True)
    print(f"Results: {out}", flush=True)
    print(f"{'='*60}", flush=True)

    print("\n=== PER-SPECIES REGION CLASSIFICATION ===", flush=True)
    for sp, sp_res in results["per_species"].items():
        for task_name, task_res in sp_res.items():
            if "error" in task_res:
                print(f"  {sp}/{task_name}: SKIPPED — {task_res['error']}", flush=True)
            else:
                print(f"  {sp}/{task_name}: AUC={task_res['probe_auc']:.3f} "
                      f"({task_res['verdict']})", flush=True)

    print("\n=== CROSS-SPECIES DISCRIMINATION ===", flush=True)
    for pair, pair_res in results["cross_species"].items():
        if "error" in pair_res:
            print(f"  {pair}: SKIPPED", flush=True)
        else:
            print(f"  {pair}: AUC={pair_res['probe_auc']:.3f} ({pair_res['verdict']})",
                  flush=True)

    print("\n=== ACTIVATOR vs REPRESSOR ===", flush=True)
    for sp, sp_res in results["signed_edges"].items():
        if "error" in sp_res:
            print(f"  {sp}: SKIPPED — {sp_res['error']}", flush=True)
        else:
            print(f"  {sp}: AUC={sp_res['probe_auc']:.3f} ({sp_res['verdict']})",
                  flush=True)

    # Total sequences processed
    total = sum(len(v) for v in all_promoters.values())
    total += sum(len(v) for v in all_coding.values())
    total += sum(len(v) for v in all_intergenic.values())
    print(f"\nTotal unique sequences through SAE: {total}", flush=True)
    print(f"Species tested: {len(SPECIES_CONFIG)}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
