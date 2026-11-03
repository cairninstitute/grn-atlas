#!/usr/bin/env python3
"""SpliceAI calibration on GRN-Atlas human gene data.

Tests what we can learn about splicing in our regulatory network:
1. TF vs non-TF splice complexity (exon counts, transcript isoforms)
2. Regulatory hub genes vs peripheral — are highly-targeted genes more complex?
3. Splice site density at regulatory target TSSs

SpliceAI local package (1.3.1) has numpy compat issues; Broad lookup API
is unreachable. So we focus on splice structure analysis using Ensembl
transcript data, which answers: does splice complexity correlate with
regulatory properties in our network?

Usage:
  python backend/scripts/calibrate_spliceai.py > /tmp/spliceai_calibration.log 2>&1
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
OUT = Path(__file__).resolve().parents[1] / "data" / "spliceai_calibration.json"

ENSEMBL_REST = "https://rest.ensembl.org"


def fetch_transcript_info(gene_symbol: str) -> list[dict] | None:
    """Fetch transcript and exon info from Ensembl for a human gene."""
    url = (f"{ENSEMBL_REST}/xrefs/symbol/homo_sapiens/{gene_symbol}"
           f"?content-type=application/json")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        gene_ids = [x["id"] for x in data if x.get("type") == "gene"]
        if not gene_ids:
            return None
        gene_id = gene_ids[0]
    except Exception:
        return None

    url = (f"{ENSEMBL_REST}/lookup/id/{gene_id}"
           f"?expand=1&content-type=application/json")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        transcripts = data.get("Transcript", [])
        result = []
        for t in transcripts:
            exons = t.get("Exon", [])
            if not exons:
                continue
            result.append({
                "transcript_id": t["id"],
                "biotype": t.get("biotype", "unknown"),
                "start": t["start"],
                "end": t["end"],
                "strand": t["strand"],
                "exons": [{"start": e["start"], "end": e["end"]} for e in exons],
            })
        return result if result else None
    except Exception:
        return None


def get_gene_splice_stats(symbol: str) -> dict | None:
    info = fetch_transcript_info(symbol)
    if not info:
        return None

    coding_txs = [t for t in info if t["biotype"] == "protein_coding"]
    all_txs = info

    max_exons = max(len(t["exons"]) for t in all_txs)
    coding_max_exons = max((len(t["exons"]) for t in coding_txs), default=0)

    # Exon size stats from longest transcript
    longest = max(all_txs, key=lambda t: len(t["exons"]))
    exon_sizes = [e["end"] - e["start"] for e in longest["exons"]]

    # Intron sizes
    sorted_exons = sorted(longest["exons"], key=lambda e: e["start"])
    intron_sizes = []
    for i in range(len(sorted_exons) - 1):
        intron_sizes.append(sorted_exons[i + 1]["start"] - sorted_exons[i]["end"])

    return {
        "symbol": symbol,
        "n_transcripts": len(all_txs),
        "n_coding_transcripts": len(coding_txs),
        "max_exons": max_exons,
        "coding_max_exons": coding_max_exons,
        "mean_exon_size": round(float(np.mean(exon_sizes)), 0) if exon_sizes else 0,
        "mean_intron_size": round(float(np.mean(intron_sizes)), 0) if intron_sizes else 0,
        "gene_span": longest["end"] - longest["start"],
    }


def main():
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA journal_mode=WAL")
    import random
    random.seed(42)

    report = {
        "model": "SpliceAI (structural analysis)",
        "note": "SpliceAI local (1.3.1) has numpy compat issue; Broad API unreachable. "
                "Analysis uses Ensembl transcript structure instead.",
        "tasks": {},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # =========================================
    # Task 1: TF vs non-TF splice complexity
    # =========================================
    print("=" * 60, flush=True)
    print("TASK 1: TF vs non-TF splice complexity (human)", flush=True)

    tf_genes = conn.execute(
        "SELECT symbol FROM genes WHERE species='human' AND is_tf=1 ORDER BY RANDOM() LIMIT 40"
    ).fetchall()
    nontf_genes = conn.execute(
        "SELECT symbol FROM genes WHERE species='human' AND is_tf=0 ORDER BY RANDOM() LIMIT 40"
    ).fetchall()

    tf_stats = []
    for (symbol,) in tf_genes:
        stats = get_gene_splice_stats(symbol)
        if stats:
            tf_stats.append(stats)
            print(f"  TF {symbol}: {stats['max_exons']} exons, "
                  f"{stats['n_transcripts']} transcripts", flush=True)
        time.sleep(0.3)

    nontf_stats = []
    for (symbol,) in nontf_genes:
        stats = get_gene_splice_stats(symbol)
        if stats:
            nontf_stats.append(stats)
            print(f"  nonTF {symbol}: {stats['max_exons']} exons, "
                  f"{stats['n_transcripts']} transcripts", flush=True)
        time.sleep(0.3)

    print(f"\nTF genes with data: {len(tf_stats)}", flush=True)
    print(f"Non-TF genes with data: {len(nontf_stats)}", flush=True)

    if tf_stats and nontf_stats:
        from scipy.stats import mannwhitneyu

        tf_exons = [s["max_exons"] for s in tf_stats]
        nontf_exons = [s["max_exons"] for s in nontf_stats]
        tf_txs = [s["n_transcripts"] for s in tf_stats]
        nontf_txs = [s["n_transcripts"] for s in nontf_stats]
        tf_introns = [s["mean_intron_size"] for s in tf_stats if s["mean_intron_size"] > 0]
        nontf_introns = [s["mean_intron_size"] for s in nontf_stats if s["mean_intron_size"] > 0]

        exon_stat, exon_p = mannwhitneyu(tf_exons, nontf_exons, alternative="two-sided")
        tx_stat, tx_p = mannwhitneyu(tf_txs, nontf_txs, alternative="two-sided")

        print(f"\n  TF exons: {np.mean(tf_exons):.1f} ± {np.std(tf_exons):.1f} "
              f"(median={np.median(tf_exons):.0f})", flush=True)
        print(f"  nonTF exons: {np.mean(nontf_exons):.1f} ± {np.std(nontf_exons):.1f} "
              f"(median={np.median(nontf_exons):.0f})", flush=True)
        print(f"  Exon count p-value: {exon_p:.4f}", flush=True)
        print(f"\n  TF transcripts: {np.mean(tf_txs):.1f} ± {np.std(tf_txs):.1f}", flush=True)
        print(f"  nonTF transcripts: {np.mean(nontf_txs):.1f} ± {np.std(nontf_txs):.1f}", flush=True)
        print(f"  Transcript count p-value: {tx_p:.4f}", flush=True)

        if tf_introns and nontf_introns:
            intron_stat, intron_p = mannwhitneyu(tf_introns, nontf_introns, alternative="two-sided")
            print(f"\n  TF mean intron: {np.mean(tf_introns):.0f} bp", flush=True)
            print(f"  nonTF mean intron: {np.mean(nontf_introns):.0f} bp", flush=True)
            print(f"  Intron size p-value: {intron_p:.4f}", flush=True)
        else:
            intron_p = None

        report["tasks"]["tf_vs_nontf_complexity"] = {
            "n_tf": len(tf_stats),
            "n_nontf": len(nontf_stats),
            "tf_mean_exons": round(float(np.mean(tf_exons)), 1),
            "tf_median_exons": float(np.median(tf_exons)),
            "nontf_mean_exons": round(float(np.mean(nontf_exons)), 1),
            "nontf_median_exons": float(np.median(nontf_exons)),
            "exon_pvalue": round(float(exon_p), 4),
            "tf_mean_transcripts": round(float(np.mean(tf_txs)), 1),
            "nontf_mean_transcripts": round(float(np.mean(nontf_txs)), 1),
            "transcript_pvalue": round(float(tx_p), 4),
            "tf_mean_intron_bp": round(float(np.mean(tf_introns)), 0) if tf_introns else None,
            "nontf_mean_intron_bp": round(float(np.mean(nontf_introns)), 0) if nontf_introns else None,
            "intron_pvalue": round(float(intron_p), 4) if intron_p is not None else None,
            "tf_details": tf_stats,
            "nontf_details": nontf_stats,
        }

    # =========================================
    # Task 2: Hub genes vs peripheral splice complexity
    # =========================================
    print(f"\n{'='*60}", flush=True)
    print("TASK 2: Regulatory hub vs peripheral gene splice complexity", flush=True)

    # Highly connected targets
    hub_genes = conn.execute("""
        SELECT g.symbol, COUNT(*) as n_edges
        FROM interactions i
        JOIN genes g ON i.target_id = g.id
        WHERE g.species = 'human'
        GROUP BY i.target_id
        HAVING n_edges >= 3
        ORDER BY n_edges DESC
        LIMIT 30
    """).fetchall()

    # Genes with exactly 1 incoming edge
    peripheral_genes = conn.execute("""
        SELECT g.symbol, COUNT(*) as n_edges
        FROM interactions i
        JOIN genes g ON i.target_id = g.id
        WHERE g.species = 'human'
        GROUP BY i.target_id
        HAVING n_edges = 1
        ORDER BY RANDOM()
        LIMIT 30
    """).fetchall()

    hub_stats = []
    for symbol, n_edges in hub_genes:
        stats = get_gene_splice_stats(symbol)
        if stats:
            stats["n_incoming_edges"] = n_edges
            hub_stats.append(stats)
            print(f"  Hub {symbol} ({n_edges} edges): {stats['max_exons']} exons", flush=True)
        time.sleep(0.3)

    peripheral_stats = []
    for symbol, n_edges in peripheral_genes:
        stats = get_gene_splice_stats(symbol)
        if stats:
            stats["n_incoming_edges"] = n_edges
            peripheral_stats.append(stats)
            print(f"  Peripheral {symbol} ({n_edges} edge): {stats['max_exons']} exons", flush=True)
        time.sleep(0.3)

    if hub_stats and peripheral_stats:
        from scipy.stats import mannwhitneyu, spearmanr

        hub_exons = [s["max_exons"] for s in hub_stats]
        peri_exons = [s["max_exons"] for s in peripheral_stats]
        hub_txs = [s["n_transcripts"] for s in hub_stats]
        peri_txs = [s["n_transcripts"] for s in peripheral_stats]

        exon_stat, exon_p = mannwhitneyu(hub_exons, peri_exons, alternative="two-sided")
        tx_stat, tx_p = mannwhitneyu(hub_txs, peri_txs, alternative="two-sided")

        # Correlation between edge count and exon count
        all_stats = hub_stats + peripheral_stats
        edges = [s["n_incoming_edges"] for s in all_stats]
        exons = [s["max_exons"] for s in all_stats]
        rho, rho_p = spearmanr(edges, exons)

        print(f"\n  Hub exons: {np.mean(hub_exons):.1f} ± {np.std(hub_exons):.1f}", flush=True)
        print(f"  Peripheral exons: {np.mean(peri_exons):.1f} ± {np.std(peri_exons):.1f}", flush=True)
        print(f"  Exon count p-value: {exon_p:.4f}", flush=True)
        print(f"  Edge-exon Spearman rho: {rho:.3f} (p={rho_p:.4f})", flush=True)

        report["tasks"]["hub_vs_peripheral_complexity"] = {
            "n_hub": len(hub_stats),
            "n_peripheral": len(peripheral_stats),
            "hub_mean_exons": round(float(np.mean(hub_exons)), 1),
            "peripheral_mean_exons": round(float(np.mean(peri_exons)), 1),
            "exon_pvalue": round(float(exon_p), 4),
            "hub_mean_transcripts": round(float(np.mean(hub_txs)), 1),
            "peripheral_mean_transcripts": round(float(np.mean(peri_txs)), 1),
            "transcript_pvalue": round(float(tx_p), 4),
            "edge_exon_spearman_rho": round(float(rho), 3),
            "edge_exon_spearman_p": round(float(rho_p), 4),
        }

    # =========================================
    # Task 3: SpliceAI published capabilities summary
    # =========================================
    report["tasks"]["spliceai_published_capabilities"] = {
        "note": "SpliceAI scores (delta scores) not computable locally due to numpy compat "
                "issue in spliceai 1.3.1 and Broad lookup API being unreachable.",
        "published_performance": {
            "top_k_accuracy": "Top-k accuracy for cryptic splicing: 56% (k=1) to 83% (k=5)",
            "delta_score_interpretation": {
                "0.0-0.2": "benign (low splice impact)",
                "0.2-0.5": "likely affects splicing",
                "0.5-0.8": "high confidence splice impact",
                "0.8-1.0": "very high confidence splice-altering",
            },
            "training_data": "Human genome, GENCODE annotations",
            "species_support": "Human only (GRCh37/GRCh38)",
        },
        "grn_atlas_relevance": {
            "potential_uses": [
                "Flag TF gene variants that may affect splicing and thus alter regulatory function",
                "Identify alternative TF isoforms with different DNA-binding properties",
                "Score variants in regulatory target genes that affect splice sites",
            ],
            "limitations": [
                "Human-only — cannot help with plant species",
                "Requires reference genome FASTA for local scoring",
                "Scores individual variants, not regulatory relationships",
            ],
            "integration_path": "Download hg38 FASTA, fix numpy compat or use newer fork, "
                               "score variants at splice junctions of TF genes in our network",
        },
    }

    # Save
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n{'='*60}", flush=True)
    print(f"Results saved to {OUT}", flush=True)

    print("\nSUMMARY:", flush=True)
    for task_name, result in report["tasks"].items():
        if "exon_pvalue" in result:
            print(f"  {task_name}: exon p={result['exon_pvalue']}", flush=True)


if __name__ == "__main__":
    main()
