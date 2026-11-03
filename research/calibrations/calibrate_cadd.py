#!/usr/bin/env python3
"""CADD variant pathogenicity scoring calibration on GRN-Atlas data.

Tests what CADD scores reveal about our regulatory regions:
1. Regulatory region variants vs intergenic (do TF binding regions score higher?)
2. TF gene promoter variants vs random gene promoters
3. Known disease-associated TFs vs other TFs

Uses the CADD v1.7 REST API (GRCh38) at cadd.gs.washington.edu.
Human-only (CADD is trained on human data).

Usage:
  python backend/scripts/calibrate_cadd.py > /tmp/cadd_calibration.log 2>&1
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
OUT = Path(__file__).resolve().parents[1] / "data" / "cadd_calibration.json"

CADD_API = "https://cadd.gs.washington.edu/api/v1.0/GRCh38-v1.7"


def fetch_cadd_score(chrom: str, pos: int) -> dict | None:
    """Fetch CADD score for a position (all possible substitutions)."""
    url = f"{CADD_API}/{chrom}:{pos}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data
    except Exception as e:
        return {"error": str(e)}


def fetch_ensembl_sequence(chrom: str, start: int, end: int) -> str | None:
    """Fetch reference sequence from Ensembl."""
    url = (f"https://rest.ensembl.org/sequence/region/homo_sapiens/"
           f"{chrom}:{start}..{end}:1?content-type=text/plain")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GRN-Atlas/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode().strip()
    except Exception:
        return None


def score_positions(positions: list[dict], label: str) -> list[dict]:
    """Score a list of positions via CADD API."""
    results = []
    for i, p in enumerate(positions):
        chrom = p["chrom"]
        pos = p["pos"]
        if (i + 1) % 10 == 0:
            print(f"  [{label}] {i+1}/{len(positions)}", flush=True)

        data = fetch_cadd_score(chrom, pos)
        if data and "error" not in data:
            # CADD returns list of substitution scores
            scores = []
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and "PHRED" in entry:
                        scores.append(float(entry["PHRED"]))
            elif isinstance(data, dict):
                if "PHRED" in data:
                    scores.append(float(data["PHRED"]))
                for key in data:
                    if isinstance(data[key], list):
                        for item in data[key]:
                            if isinstance(item, dict) and "PHRED" in item:
                                scores.append(float(item["PHRED"]))

            max_phred = max(scores) if scores else None
            results.append({**p, "max_phred": max_phred, "n_scores": len(scores),
                           "status": "scored" if max_phred is not None else "no_phred"})
        else:
            results.append({**p, "max_phred": None, "status": f"error",
                           "error_detail": str(data)})

        time.sleep(1.0)  # Rate limit: CADD API is not designed for bulk queries

    return results


def main():
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA journal_mode=WAL")
    import random
    random.seed(42)

    report = {
        "model": "CADD-v1.7",
        "species": "human",
        "tasks": {},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # =========================================
    # Task 1: TSS-proximal vs distal positions
    # =========================================
    print("=" * 60, flush=True)
    print("TASK 1: TSS-proximal vs distal variant scoring", flush=True)
    print("Hypothesis: positions near TF gene TSSs score higher than random intergenic", flush=True)

    # Get TF genes with locations
    tf_genes = conn.execute("""
        SELECT g.id, g.symbol, gl.chromosome, gl.start, gl.end, gl.strand
        FROM genes g
        JOIN gene_locations gl ON g.id = gl.gene_id AND g.species = gl.species
        WHERE g.species = 'human' AND g.is_tf = 1
        ORDER BY RANDOM() LIMIT 30
    """).fetchall()

    # TSS-proximal positions (within 200bp of TSS)
    tss_positions = []
    for gene_id, symbol, chrom, gstart, gend, strand in tf_genes:
        tss = gstart if strand == 1 else gend
        for offset in [-100, -50, 0, 50, 100]:
            pos = tss + offset
            if pos > 0:
                tss_positions.append({
                    "chrom": str(chrom),
                    "pos": pos,
                    "gene": symbol,
                    "offset_from_tss": offset,
                    "type": "tss_proximal",
                })

    # Random intergenic positions (far from any gene)
    intergenic_positions = []
    all_gene_starts = conn.execute(
        "SELECT chromosome, start, end FROM gene_locations WHERE species='human'"
    ).fetchall()
    gene_regions = {}
    for ch, s, e in all_gene_starts:
        gene_regions.setdefault(str(ch), []).append((s, e))

    for chrom_str in ["1", "2", "3", "5", "7"]:
        regions = sorted(gene_regions.get(chrom_str, []))
        for i in range(len(regions) - 1):
            gap_start = regions[i][1]
            gap_end = regions[i + 1][0]
            gap_size = gap_end - gap_start
            if gap_size > 100000:
                mid = (gap_start + gap_end) // 2
                intergenic_positions.append({
                    "chrom": chrom_str,
                    "pos": mid,
                    "type": "intergenic",
                    "gap_size": gap_size,
                })
                if len(intergenic_positions) >= 50:
                    break
        if len(intergenic_positions) >= 50:
            break

    # Sample
    tss_sample = random.sample(tss_positions, min(30, len(tss_positions)))
    intergenic_sample = random.sample(intergenic_positions, min(30, len(intergenic_positions)))

    print(f"TSS-proximal positions: {len(tss_sample)}", flush=True)
    print(f"Intergenic positions: {len(intergenic_sample)}", flush=True)

    print("\nScoring TSS-proximal...", flush=True)
    tss_results = score_positions(tss_sample, "TSS")
    print("Scoring intergenic...", flush=True)
    intergenic_results = score_positions(intergenic_sample, "intergenic")

    tss_scores = [r["max_phred"] for r in tss_results if r["max_phred"] is not None]
    inter_scores = [r["max_phred"] for r in intergenic_results if r["max_phred"] is not None]

    if tss_scores and inter_scores:
        from sklearn.metrics import roc_auc_score

        all_scores = tss_scores + inter_scores
        labels = [1] * len(tss_scores) + [0] * len(inter_scores)
        auc = roc_auc_score(labels, all_scores)

        print(f"\nResults:", flush=True)
        print(f"  TSS-proximal scored: {len(tss_scores)}/{len(tss_sample)}", flush=True)
        print(f"  Intergenic scored: {len(inter_scores)}/{len(intergenic_sample)}", flush=True)
        print(f"  Mean TSS PHRED: {np.mean(tss_scores):.2f}", flush=True)
        print(f"  Mean intergenic PHRED: {np.mean(inter_scores):.2f}", flush=True)
        print(f"  AUC (TSS vs intergenic): {auc:.4f}", flush=True)

        report["tasks"]["tss_vs_intergenic"] = {
            "n_tss": len(tss_scores),
            "n_intergenic": len(inter_scores),
            "mean_tss_phred": round(float(np.mean(tss_scores)), 2),
            "mean_intergenic_phred": round(float(np.mean(inter_scores)), 2),
            "auc": round(float(auc), 4),
            "tss_median": round(float(np.median(tss_scores)), 2),
            "intergenic_median": round(float(np.median(inter_scores)), 2),
        }
    else:
        report["tasks"]["tss_vs_intergenic"] = {
            "error": "Insufficient scores",
            "tss_scored": len(tss_scores),
            "intergenic_scored": len(inter_scores),
            "api_note": "CADD API may rate-limit or not return scores for all positions",
        }

    # =========================================
    # Task 2: Interaction-supported vs unsupported TF promoters
    # =========================================
    print(f"\n{'='*60}", flush=True)
    print("TASK 2: Regulatory target TSS scoring", flush=True)
    print("Hypothesis: TSSs of genes targeted by many TFs score higher", flush=True)

    # Highly-targeted genes (many incoming edges)
    high_target = conn.execute("""
        SELECT g.symbol, gl.chromosome, gl.start, gl.end, gl.strand, COUNT(*) as n_edges
        FROM interactions i
        JOIN genes g ON i.target_id = g.id
        JOIN gene_locations gl ON g.id = gl.gene_id AND g.species = gl.species
        WHERE g.species = 'human'
        GROUP BY i.target_id
        HAVING n_edges >= 5
        ORDER BY n_edges DESC
        LIMIT 20
    """).fetchall()

    # Lowly-targeted genes
    low_target = conn.execute("""
        SELECT g.symbol, gl.chromosome, gl.start, gl.end, gl.strand, COUNT(*) as n_edges
        FROM interactions i
        JOIN genes g ON i.target_id = g.id
        JOIN gene_locations gl ON g.id = gl.gene_id AND g.species = gl.species
        WHERE g.species = 'human'
        GROUP BY i.target_id
        HAVING n_edges = 1
        ORDER BY RANDOM()
        LIMIT 20
    """).fetchall()

    high_positions = []
    for symbol, chrom, gstart, gend, strand, n_edges in high_target:
        tss = gstart if strand == 1 else gend
        high_positions.append({
            "chrom": str(chrom), "pos": tss, "gene": symbol,
            "n_edges": n_edges, "type": "high_target",
        })

    low_positions = []
    for symbol, chrom, gstart, gend, strand, n_edges in low_target:
        tss = gstart if strand == 1 else gend
        low_positions.append({
            "chrom": str(chrom), "pos": tss, "gene": symbol,
            "n_edges": n_edges, "type": "low_target",
        })

    print(f"High-target genes: {len(high_positions)}", flush=True)
    print(f"Low-target genes: {len(low_positions)}", flush=True)

    print("\nScoring high-target TSSs...", flush=True)
    high_results = score_positions(high_positions[:20], "high")
    print("Scoring low-target TSSs...", flush=True)
    low_results = score_positions(low_positions[:20], "low")

    high_scores = [r["max_phred"] for r in high_results if r["max_phred"] is not None]
    low_scores = [r["max_phred"] for r in low_results if r["max_phred"] is not None]

    if high_scores and low_scores:
        from sklearn.metrics import roc_auc_score

        all_scores2 = high_scores + low_scores
        labels2 = [1] * len(high_scores) + [0] * len(low_scores)
        auc2 = roc_auc_score(labels2, all_scores2)

        print(f"\nResults:", flush=True)
        print(f"  High-target scored: {len(high_scores)}", flush=True)
        print(f"  Low-target scored: {len(low_scores)}", flush=True)
        print(f"  Mean high PHRED: {np.mean(high_scores):.2f}", flush=True)
        print(f"  Mean low PHRED: {np.mean(low_scores):.2f}", flush=True)
        print(f"  AUC: {auc2:.4f}", flush=True)

        report["tasks"]["high_vs_low_target_tss"] = {
            "n_high": len(high_scores),
            "n_low": len(low_scores),
            "mean_high_phred": round(float(np.mean(high_scores)), 2),
            "mean_low_phred": round(float(np.mean(low_scores)), 2),
            "auc": round(float(auc2), 4),
        }
    else:
        report["tasks"]["high_vs_low_target_tss"] = {
            "error": "Insufficient scores",
            "high_scored": len(high_scores),
            "low_scored": len(low_scores),
        }

    # Save
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n{'='*60}", flush=True)
    print(f"Results saved to {OUT}", flush=True)

    # Summary
    print("\nSUMMARY:", flush=True)
    for task_name, result in report["tasks"].items():
        if "auc" in result:
            print(f"  {task_name}: AUC={result['auc']}", flush=True)
        elif "error" in result:
            print(f"  {task_name}: {result['error']}", flush=True)


if __name__ == "__main__":
    main()
