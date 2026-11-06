#!/usr/bin/env python3
"""Load RAP-DB → MSU LOC crosswalk as gene aliases for rice.

Uses the Ensembl Plants GFF3 for RAP-DB gene coordinates and the MSU/RGAP
locus annotation for LOC_Os coordinates, matching by genomic overlap.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import sqlite3
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"

GFF3_URL = (
    "https://ftp.ebi.ac.uk/ensemblgenomes/pub/plants/current/gff3/"
    "oryza_sativa/Oryza_sativa.IRGSP-1.0.63.chr.gff3.gz"
)
RGAP_URL = (
    "http://rice.uga.edu/pub/data/Eukaryotic_Projects/o_sativa/"
    "annotation_dbs/pseudomolecules/version_7.0/all.dir/all.locus_brief_info.7.0"
)
UA = {"User-Agent": "grn-atlas/1.0"}


def fetch_rap_coordinates() -> dict[str, tuple[str, int, int, str]]:
    req = urllib.request.Request(GFF3_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as resp:
        raw = gzip.decompress(resp.read())
    genes = {}
    for line in raw.decode("utf-8", "replace").split("\n"):
        if line.startswith("#") or "\tgene\t" not in line:
            continue
        parts = line.split("\t")
        if parts[2] != "gene":
            continue
        m = re.search(r"gene_id=(Os\d+g\d+)", parts[8])
        if m:
            genes[m.group(1)] = (parts[0], int(parts[3]), int(parts[4]), parts[6])
    return genes


def fetch_msu_coordinates() -> dict[str, tuple[str, int, int, str]]:
    req = urllib.request.Request(RGAP_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        text = resp.read().decode("utf-8", "replace")
    loci = {}
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for row in reader:
        locus = row.get("locus", "")
        if not locus.startswith("LOC_Os"):
            continue
        if row.get("is_representative", "") != "Y":
            continue
        chrom = row["chr"].replace("Chr", "").replace("chr", "")
        loci[locus] = (chrom, int(row["start"]), int(row["stop"]), row["ori"])
    return loci


def build_crosswalk(
    rap: dict[str, tuple], msu: dict[str, tuple]
) -> dict[str, str]:
    msu_by_chrom: dict[str, list] = defaultdict(list)
    for locus, (chrom, start, end, strand) in msu.items():
        msu_by_chrom[chrom].append((start, end, strand, locus))
    for chrom in msu_by_chrom:
        msu_by_chrom[chrom].sort()

    crosswalk = {}
    for rap_id, (chrom, rstart, rend, rstrand) in rap.items():
        best_overlap = 0
        best_msu = None
        for mstart, mend, mstrand, locus in msu_by_chrom.get(chrom, []):
            if mstrand != rstrand:
                continue
            if mstart > rend + 500:
                break
            if mend < rstart - 500:
                continue
            overlap = min(rend, mend) - max(rstart, mstart)
            if overlap > best_overlap:
                best_overlap = overlap
                best_msu = locus
        if best_msu:
            crosswalk[rap_id] = best_msu
    return crosswalk


def load_aliases(conn: sqlite3.Connection, crosswalk: dict[str, str]) -> dict:
    our_genes = {
        r[0]
        for r in conn.execute(
            "SELECT id FROM genes WHERE species='rice'"
        ).fetchall()
    }
    conn.execute("DELETE FROM gene_aliases WHERE source='RAP-DB'")
    inserted = 0
    for rap_id, msu_id in crosswalk.items():
        if msu_id in our_genes:
            conn.execute(
                "INSERT OR IGNORE INTO gene_aliases (gene_id, alias, source) "
                "VALUES (?, ?, 'RAP-DB')",
                (msu_id, rap_id),
            )
            inserted += 1
    conn.commit()
    return {
        "rap_genes_total": len(crosswalk),
        "mapped_to_atlas": inserted,
        "rice_genes_in_atlas": len(our_genes),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()

    print("Fetching RAP-DB gene coordinates from Ensembl Plants GFF3...")
    rap = fetch_rap_coordinates()
    print(f"  {len(rap)} RAP-DB genes")

    print("Fetching MSU/RGAP locus coordinates...")
    msu = fetch_msu_coordinates()
    print(f"  {len(msu)} MSU representative loci")

    print("Building RAP→MSU crosswalk by coordinate overlap...")
    crosswalk = build_crosswalk(rap, msu)
    print(f"  {len(crosswalk)} matched pairs")

    with sqlite3.connect(args.db) as conn:
        stats = load_aliases(conn, crosswalk)

    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
