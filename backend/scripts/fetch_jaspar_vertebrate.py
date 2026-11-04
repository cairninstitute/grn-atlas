#!/usr/bin/env python3
"""Fetch JASPAR 2024 vertebrate motifs and scan human/mouse TF binding sites.

Downloads the JASPAR CORE vertebrate non-redundant PFMs, maps them to
atlas TFs, and stores in the motifs table. Then scans human/mouse promoter
sequences for motif hits to create evidence for base-resolution binding.

Usage:
    python backend/scripts/fetch_jaspar_vertebrate.py [--db PATH] [--scan]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
DATA_DIR = BACKEND / "data" / "external_sources"

JASPAR_URL = (
    "https://jaspar.elixir.no/download/data/2024/CORE/"
    "JASPAR2024_CORE_vertebrates_non-redundant_pfms_jaspar.txt"
)
SOURCE = "JASPAR2024_vertebrate"
UA = {"User-Agent": "grn-atlas/1.0"}


def download_jaspar(out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    partial = out_path.with_suffix(out_path.suffix + ".part")
    req = urllib.request.Request(JASPAR_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp, partial.open("wb") as fh:
        shutil.copyfileobj(resp, fh)
    partial.replace(out_path)
    matrices = sum(1 for line in out_path.open() if line.startswith(">"))
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    meta = out_path.with_suffix(".metadata.json")
    meta.write_text(json.dumps({
        "url": JASPAR_URL, "sha256": digest, "matrices": matrices,
        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=2))
    return matrices


def parse_jaspar_file(path: Path) -> list[dict]:
    motifs = []
    current_id = None
    current_name = None
    current_matrix: list[list[float]] = []

    for line in path.open():
        line = line.strip()
        if line.startswith(">"):
            if current_id and current_matrix:
                motifs.append({
                    "jaspar_id": current_id, "name": current_name,
                    "matrix": current_matrix,
                })
            match = re.match(r">(\S+)\s+(.+)", line)
            if match:
                current_id = match.group(1)
                current_name = match.group(2).strip()
            current_matrix = []
        elif line.startswith(("[", "A", "C", "G", "T")):
            row_match = re.findall(r"[\d.]+", line)
            if row_match:
                current_matrix.append([float(x) for x in row_match])

    if current_id and current_matrix:
        motifs.append({"jaspar_id": current_id, "name": current_name, "matrix": current_matrix})

    return motifs


def map_motifs_to_tfs(conn: sqlite3.Connection, motifs: list[dict]) -> list[dict]:
    tf_symbols = {}
    for gene_id, symbol, species in conn.execute(
        "SELECT id, symbol, species FROM genes WHERE is_tf = 1 AND species IN ('human', 'mouse')"
    ):
        if symbol:
            tf_symbols[symbol.upper()] = gene_id

    mapped = []
    for m in motifs:
        name_upper = m["name"].upper().split("::")[0].strip()
        name_variants = [name_upper, name_upper.replace("-", ""), name_upper.replace(".", "")]
        gene_id = None
        for v in name_variants:
            if v in tf_symbols:
                gene_id = tf_symbols[v]
                break

        mapped.append({
            **m,
            "tf_gene_id": gene_id,
            "tf_symbol": m["name"].split("::")[0].strip(),
        })

    return mapped


def store_motifs(conn: sqlite3.Connection, motifs: list[dict]) -> Counter:
    stats = Counter()
    for m in motifs:
        motif_id = f"JASPAR_vert_{m['jaspar_id']}"
        conn.execute(
            "INSERT OR REPLACE INTO motifs (motif_id, source, jaspar_id, tf_gene_id, tf_symbol) "
            "VALUES (?, ?, ?, ?, ?)",
            (motif_id, SOURCE, m["jaspar_id"], m.get("tf_gene_id"), m["tf_symbol"]))
        stats["stored"] += 1
        if m.get("tf_gene_id"):
            stats["mapped_to_tf"] += 1
        else:
            stats["unmapped"] += 1
    conn.commit()
    return stats


def scan_promoters(conn: sqlite3.Connection, motifs: list[dict]) -> Counter:
    """Scan human/mouse promoter DNA sequences against vertebrate motifs."""
    import numpy as np

    stats = Counter()

    promoters = conn.execute("""
        SELECT gene_id, species, sequence
        FROM promoter_dna_sequences
        WHERE fetch_status = 'found' AND sequence IS NOT NULL
          AND species IN ('human', 'mouse')
    """).fetchall()

    if not promoters:
        print("  No human/mouse promoter sequences to scan.")
        return stats

    print(f"  Scanning {len(promoters)} promoters against {len(motifs)} motifs...")

    mapped_motifs = [m for m in motifs if m.get("tf_gene_id")]
    if not mapped_motifs:
        print("  No motifs mapped to human/mouse TFs.")
        return stats

    base_idx = {"A": 0, "C": 1, "G": 2, "T": 3}

    for pi, (gene_id, species, seq) in enumerate(promoters):
        seq = seq.upper()
        if len(seq) < 8:
            continue

        for m in mapped_motifs:
            matrix = m["matrix"]
            if len(matrix) != 4 or not matrix[0]:
                continue
            motif_len = len(matrix[0])
            if motif_len > len(seq):
                continue

            pfm = np.array(matrix)
            pfm = pfm / pfm.sum(axis=0, keepdims=True)
            pwm = np.log2((pfm + 0.01) / 0.25)

            best_score = -999
            for pos in range(len(seq) - motif_len + 1):
                score = 0.0
                valid = True
                for j in range(motif_len):
                    idx = base_idx.get(seq[pos + j])
                    if idx is None:
                        valid = False
                        break
                    score += pwm[idx, j]
                if valid:
                    best_score = max(best_score, score)

            max_possible = pwm.max(axis=0).sum()
            if max_possible > 0:
                rel_score = best_score / max_possible
            else:
                continue

            if rel_score >= 0.80:
                motif_id = f"JASPAR_vert_{m['jaspar_id']}"
                conn.execute(
                    "INSERT OR IGNORE INTO motif_hits "
                    "(ext_gene_id, motif_id, assembly, window_type, chromosome, start, \"end\", strand, score, tier, site_confidence) "
                    "VALUES (?, ?, ?, 'promoter_200bp', 'scan', 0, 0, 1, ?, ?, ?)",
                    (gene_id, motif_id, species, best_score, "vertebrate_scan", rel_score))
                stats["hits"] += 1

        stats["promoters_scanned"] += 1
        if (pi + 1) % 20 == 0:
            conn.commit()
            print(f"    [{pi + 1}/{len(promoters)}] {stats['hits']} hits")

    conn.commit()
    return stats


def ensure_motif_hits_table(conn: sqlite3.Connection) -> None:
    pass


def main():
    parser = argparse.ArgumentParser(description="Fetch JASPAR vertebrate motifs")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--scan", action="store_true", help="Also scan promoter sequences")
    args = parser.parse_args()

    jaspar_file = DATA_DIR / "JASPAR2024_CORE_vertebrates.jaspar"

    print("Phase 1: Download JASPAR vertebrate motifs...")
    n = download_jaspar(jaspar_file)
    print(f"  Downloaded {n} matrices")

    print("\nPhase 2: Parse and map to atlas TFs...")
    motifs = parse_jaspar_file(jaspar_file)
    print(f"  Parsed {len(motifs)} motifs")

    conn = sqlite3.connect(str(args.db))
    ensure_motif_hits_table(conn)

    mapped = map_motifs_to_tfs(conn, motifs)
    stats = store_motifs(conn, mapped)
    print(f"  Stored: {stats['stored']} ({stats['mapped_to_tf']} mapped to TFs, {stats['unmapped']} unmapped)")

    if args.scan:
        print("\nPhase 3: Scanning promoter sequences for motif hits...")
        scan_stats = scan_promoters(conn, mapped)
        print(f"  Promoters scanned: {scan_stats.get('promoters_scanned', 0)}")
        print(f"  Motif hits: {scan_stats.get('hits', 0)}")

    # Summary
    print("\nMotifs table summary:")
    for source, count in conn.execute("SELECT source, COUNT(*) FROM motifs GROUP BY source"):
        print(f"  {source}: {count}")

    total = conn.execute("SELECT COUNT(*) FROM motif_hits").fetchone()[0]
    print(f"\nTotal motif_hits: {total}")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
