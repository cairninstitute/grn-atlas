#!/usr/bin/env python3
"""ProteinMPNN sequence design calibration on GRN-Atlas TF structures.

Tests what ProteinMPNN reveals about TF protein designability:
1. Sequence recovery: does ProteinMPNN recover the native TF sequence?
   Higher recovery = more structurally constrained/designable protein.
2. TF vs non-TF: are TF proteins more or less designable?
3. Per-residue recovery at DNA-binding domains vs other regions.

Downloads AlphaFold PDB structures, then scores with ProteinMPNN.

Usage:
  python backend/scripts/calibrate_proteinmpnn.py > /tmp/proteinmpnn_calibration.log 2>&1
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import torch

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
OUT = Path(__file__).resolve().parents[1] / "data" / "proteinmpnn_calibration.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict_structural_binding import SPECIES_CONFIG

AF_API = "https://alphafold.ebi.ac.uk/api"
PDB_CACHE = Path("/tmp/alphafold_pdbs")
PDB_CACHE.mkdir(exist_ok=True)


def get_uniprot_accession(gene_symbol: str, species: str) -> str | None:
    cfg = SPECIES_CONFIG.get(species, {})
    taxon = cfg.get("taxon_id")
    if not taxon:
        return None
    url = (f"https://rest.uniprot.org/uniprotkb/search?"
           f"query=gene:{gene_symbol}+AND+taxonomy_id:{taxon}"
           f"&format=json&size=1&fields=accession")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        if results:
            return results[0]["primaryAccession"]
    except Exception:
        return None


def download_af_pdb(uniprot_acc: str) -> Path | None:
    pdb_path = PDB_CACHE / f"AF-{uniprot_acc}-F1-model_v4.pdb"
    if pdb_path.exists() and pdb_path.stat().st_size > 100:
        return pdb_path

    # Get entry info first
    url = f"{AF_API}/prediction/{uniprot_acc}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, list) and data:
            pdb_url = data[0].get("pdbUrl")
            if pdb_url:
                req2 = urllib.request.Request(pdb_url, headers={"User-Agent": "GRN-Atlas/1.0"})
                with urllib.request.urlopen(req2, timeout=30) as resp2:
                    pdb_path.write_bytes(resp2.read())
                return pdb_path
    except Exception:
        pass
    return None


def parse_pdb_sequence(pdb_path: Path) -> str:
    """Extract single-letter amino acid sequence from PDB ATOM records."""
    aa_map = {
        "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
        "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
        "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
        "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
    }
    residues = {}
    with open(pdb_path) as f:
        for line in f:
            if line.startswith("ATOM") and line[12:16].strip() == "CA":
                resname = line[17:20].strip()
                resnum = int(line[22:26].strip())
                chain = line[21]
                if chain == "A" and resname in aa_map:
                    residues[resnum] = aa_map[resname]
    return "".join(residues[k] for k in sorted(residues))


_mpnn_model = None
_mpnn_device = None


def get_mpnn_model():
    global _mpnn_model, _mpnn_device
    if _mpnn_model is not None:
        return _mpnn_model, _mpnn_device

    from proteinmpnn.protein_mpnn_utils import ProteinMPNN
    import proteinmpnn.data.vanilla_model_weights as weights_module

    weights_dir = Path(weights_module.__file__).parent
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    checkpoint = torch.load(
        weights_dir / "v_48_020.pt",
        map_location=device, weights_only=False
    )

    model = ProteinMPNN(
        num_letters=21, node_features=128, edge_features=128,
        hidden_dim=128, num_encoder_layers=3, num_decoder_layers=3,
        vocab=21, k_neighbors=48, augment_eps=0.0,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device).eval()
    _mpnn_model = model
    _mpnn_device = device
    print(f"ProteinMPNN loaded on {device}", flush=True)
    return model, device


def score_with_proteinmpnn(pdb_path: Path) -> dict | None:
    """Score a PDB structure with ProteinMPNN and measure sequence recovery."""
    try:
        from proteinmpnn.protein_mpnn_utils import parse_PDB, tied_featurize

        model, device = get_mpnn_model()

        native_seq = parse_pdb_sequence(pdb_path)
        if len(native_seq) < 20:
            return None

        pdb_dict_list = parse_PDB(str(pdb_path))
        if not pdb_dict_list or not pdb_dict_list[0].get("seq"):
            return None

        X, S, mask, lengths, chain_M, chain_encoding_all, \
            chain_list_list, visible_list_list, masked_list_list, \
            masked_chain_length_list_list, chain_M_pos, omit_AA_mask, \
            residue_idx, dihedral_mask, tied_pos_list_of_lists_list, \
            pssm_coef, pssm_bias, pssm_log_odds_all, bias_by_res_all, \
            tied_beta = tied_featurize(
                pdb_dict_list, device, chain_dict=None
            )

        randn = torch.randn(chain_M.shape, device=device)

        with torch.no_grad():
            log_probs = model(X, S, mask, chain_M * chain_M_pos,
                              residue_idx, chain_encoding_all, randn)

        predicted = torch.argmax(log_probs, dim=-1)
        matches = (predicted == S) * mask * chain_M * chain_M_pos
        n_residues = (mask * chain_M * chain_M_pos).sum().item()

        if n_residues > 0:
            recovery = matches.sum().item() / n_residues
            S_onehot = torch.nn.functional.one_hot(S, 21).float()
            native_log_prob = (log_probs * S_onehot).sum(-1)
            mean_log_prob = (native_log_prob * mask * chain_M * chain_M_pos).sum().item() / n_residues
            perplexity = np.exp(-mean_log_prob)
            return {
                "recovery": round(float(recovery), 4),
                "perplexity": round(float(perplexity), 2),
                "mean_log_prob": round(float(mean_log_prob), 4),
                "n_residues": int(n_residues),
                "seq_length": len(native_seq),
            }

    except Exception as e:
        print(f"    ProteinMPNN error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None


NONTF_HUMAN_ACCESSIONS = {
    "GAPDH": "P04406", "ACTB": "P60709", "TUBB": "P07437",
    "HSP90AA1": "P07900", "HSPA8": "P11142", "PKM": "P14618",
    "ENO1": "P06733", "LDHA": "P00338", "ALDOA": "P04075",
    "TPI1": "P60174", "PGK1": "P00558", "GPI": "P06744",
    "PPIA": "P62937", "UBC": "P0CG48", "RPS27A": "P62979",
    "EEF1A1": "P68104", "EEF2": "P13639", "RPL7": "P18124",
    "RPS3": "P23396", "ATP5F1B": "P06576",
}


def score_accession(acc: str, symbol: str, label: str) -> dict | None:
    pdb = download_af_pdb(acc)
    if not pdb:
        print(f"  {label} {symbol} ({acc}): no AlphaFold PDB", flush=True)
        return None
    time.sleep(0.1)

    result = score_with_proteinmpnn(pdb)
    if result:
        result["symbol"] = symbol
        result["uniprot_acc"] = acc
        print(f"  {label} {symbol}: recovery={result['recovery']:.3f}, "
              f"perplexity={result['perplexity']:.1f}", flush=True)
        return result
    else:
        print(f"  {label} {symbol}: scoring failed", flush=True)
        return None


def main():
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA journal_mode=WAL")

    report = {
        "model": "ProteinMPNN (sequence design scoring)",
        "tasks": {},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # =========================================
    # Task 1: TF vs non-TF designability
    # Uses cached accessions from protein_sequences table for TFs
    # and hardcoded housekeeping protein accessions for non-TFs
    # =========================================
    print("=" * 60, flush=True)
    print("TASK 1: TF vs non-TF designability", flush=True)

    tf_rows = conn.execute("""
        SELECT g.symbol, ps.uniprot_acc, g.species
        FROM protein_sequences ps
        JOIN genes g ON ps.gene_id = g.id AND ps.species = g.species
        WHERE ps.fetch_status = 'found' AND g.is_tf = 1
        ORDER BY RANDOM() LIMIT 30
    """).fetchall()

    tf_scores = []
    for symbol, acc, species in tf_rows:
        r = score_accession(acc, symbol, f"TF({species})")
        if r:
            r["species"] = species
            tf_scores.append(r)

    nontf_scores = []
    for symbol, acc in NONTF_HUMAN_ACCESSIONS.items():
        r = score_accession(acc, symbol, "nonTF")
        if r:
            r["species"] = "human"
            nontf_scores.append(r)

    print(f"\nTF scored: {len(tf_scores)}, nonTF scored: {len(nontf_scores)}", flush=True)

    if len(tf_scores) >= 5 and len(nontf_scores) >= 5:
        from sklearn.metrics import roc_auc_score
        from scipy.stats import mannwhitneyu

        tf_rec = [s["recovery"] for s in tf_scores]
        nontf_rec = [s["recovery"] for s in nontf_scores]
        tf_ppl = [s["perplexity"] for s in tf_scores]
        nontf_ppl = [s["perplexity"] for s in nontf_scores]

        rec_stat, rec_p = mannwhitneyu(tf_rec, nontf_rec, alternative="two-sided")
        ppl_stat, ppl_p = mannwhitneyu(tf_ppl, nontf_ppl, alternative="two-sided")

        all_rec = tf_rec + nontf_rec
        labels = [1] * len(tf_rec) + [0] * len(nontf_rec)
        auc_rec = roc_auc_score(labels, all_rec)

        print(f"\n  TF recovery: {np.mean(tf_rec):.3f} +/- {np.std(tf_rec):.3f}", flush=True)
        print(f"  nonTF recovery: {np.mean(nontf_rec):.3f} +/- {np.std(nontf_rec):.3f}", flush=True)
        print(f"  Recovery AUC: {auc_rec:.4f}, p={rec_p:.4f}", flush=True)
        print(f"  TF perplexity: {np.mean(tf_ppl):.1f} +/- {np.std(tf_ppl):.1f}", flush=True)
        print(f"  nonTF perplexity: {np.mean(nontf_ppl):.1f} +/- {np.std(nontf_ppl):.1f}", flush=True)
        print(f"  Perplexity p={ppl_p:.4f}", flush=True)

        report["tasks"]["tf_vs_nontf_designability"] = {
            "n_tf": len(tf_scores),
            "n_nontf": len(nontf_scores),
            "tf_mean_recovery": round(float(np.mean(tf_rec)), 4),
            "nontf_mean_recovery": round(float(np.mean(nontf_rec)), 4),
            "recovery_auc": round(float(auc_rec), 4),
            "recovery_pvalue": round(float(rec_p), 4),
            "tf_mean_perplexity": round(float(np.mean(tf_ppl)), 2),
            "nontf_mean_perplexity": round(float(np.mean(nontf_ppl)), 2),
            "perplexity_pvalue": round(float(ppl_p), 4),
            "tf_scores": tf_scores,
            "nontf_scores": nontf_scores,
        }

    # =========================================
    # Task 2: TF family designability (arabidopsis)
    # =========================================
    print(f"\n{'='*60}", flush=True)
    print("TASK 2: TF family designability (arabidopsis)", flush=True)

    families = {"WRKY": "WRKY%", "MYB": "MYB%", "bHLH": "bHLH%",
                "ERF": "ERF%", "NAC": "NAC%", "bZIP": "bZIP%"}

    family_scores = {}
    for fam_name, pattern in families.items():
        rows = conn.execute("""
            SELECT g.symbol, ps.uniprot_acc
            FROM protein_sequences ps
            JOIN genes g ON ps.gene_id = g.id AND ps.species = g.species
            WHERE ps.fetch_status = 'found' AND g.is_tf = 1
              AND g.species = 'arabidopsis' AND g.symbol LIKE ?
            ORDER BY RANDOM() LIMIT 10
        """, (pattern,)).fetchall()

        scores = []
        for symbol, acc in rows:
            r = score_accession(acc, symbol, fam_name)
            if r:
                scores.append(r)
        if scores:
            family_scores[fam_name] = scores
            recs = [s["recovery"] for s in scores]
            ppls = [s["perplexity"] for s in scores]
            print(f"  {fam_name}: n={len(scores)}, recovery={np.mean(recs):.3f}, "
                  f"perplexity={np.mean(ppls):.1f}", flush=True)

    # Pairwise comparison
    fam_results = {}
    fam_names = list(family_scores.keys())
    for i in range(len(fam_names)):
        for j in range(i + 1, len(fam_names)):
            f1, f2 = fam_names[i], fam_names[j]
            s1, s2 = family_scores[f1], family_scores[f2]
            if len(s1) < 3 or len(s2) < 3:
                continue
            from scipy.stats import mannwhitneyu
            rec1 = [s["recovery"] for s in s1]
            rec2 = [s["recovery"] for s in s2]
            try:
                stat, p = mannwhitneyu(rec1, rec2, alternative="two-sided")
                pair = f"{f1}_vs_{f2}"
                fam_results[pair] = {
                    "f1_mean_recovery": round(float(np.mean(rec1)), 4),
                    "f2_mean_recovery": round(float(np.mean(rec2)), 4),
                    "pvalue": round(float(p), 4),
                }
                print(f"    {pair}: p={p:.4f}", flush=True)
            except Exception:
                pass

    report["tasks"]["tf_family_designability"] = {
        "species": "arabidopsis",
        "families": {k: {"n": len(v),
                         "mean_recovery": round(float(np.mean([s["recovery"] for s in v])), 4),
                         "mean_perplexity": round(float(np.mean([s["perplexity"] for s in v])), 2)}
                     for k, v in family_scores.items()},
        "pairwise": fam_results,
    }

    # Save
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n{'='*60}", flush=True)
    print(f"Results saved to {OUT}", flush=True)


if __name__ == "__main__":
    main()
