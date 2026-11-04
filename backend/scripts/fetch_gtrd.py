#!/usr/bin/env python3
"""Fetch TF-target binding edges from GTRD (Gene Transcription Regulation Database).

GTRD provides uniformly processed ChIP-seq data for human and mouse TFs.
This script tries both the download API and direct file URLs.

Output: backend/data/direct_binding/gtrd_{species}.tsv
Format: tf_symbol\ttarget_id\tsource\taccession\tconfidence
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND / "data" / "direct_binding"

GTRD_META_URL = "https://gtrd.biouml.org/api/data"
GTRD_DOWNLOAD_URLS = {
    "human": [
        "https://gtrd.biouml.org/downloads/current/intervals/target_genes/Homo_sapiens_target_genes.interval.gz",
        "https://gtrd.biouml.org/downloads/current/target_genes/Homo_sapiens_target_genes.tsv.gz",
        "https://gtrd20.biouml.org/downloads/current/target_genes/Homo_sapiens_target_genes.tsv.gz",
    ],
    "mouse": [
        "https://gtrd.biouml.org/downloads/current/intervals/target_genes/Mus_musculus_target_genes.interval.gz",
        "https://gtrd.biouml.org/downloads/current/target_genes/Mus_musculus_target_genes.tsv.gz",
        "https://gtrd20.biouml.org/downloads/current/target_genes/Mus_musculus_target_genes.tsv.gz",
    ],
}

GTRD_API_TARGETS = "https://gtrd.biouml.org/api/table/data/databases/GTRD/Data/target genes/{tf}?from=0&to=500"


def try_download(url: str, timeout: int = 60) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read()
    except Exception as e:
        print(f"  FAILED: {url} -> {e}")
        return None


def try_gtrd_api_tf_list(timeout: int = 30) -> list[str] | None:
    url = "https://gtrd.biouml.org/api/table/data/databases/GTRD/Data/transcription%20factors?from=0&to=100"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        if data.get("type") == 0 and "values" in data:
            return [row[0] for row in data["values"]]
    except Exception as e:
        print(f"  GTRD API unavailable: {e}")
    return None


def fetch_species(species: str, output: Path) -> dict:
    stats = {"species": species, "status": "failed", "edges": 0, "tfs": 0}

    # Try bulk download first
    print(f"\n[GTRD] Trying bulk download for {species}...")
    for url in GTRD_DOWNLOAD_URLS.get(species, []):
        data = try_download(url, timeout=120)
        if data is not None:
            print(f"  Downloaded {len(data)} bytes from {url}")
            try:
                if url.endswith(".gz"):
                    text = gzip.decompress(data).decode("utf-8")
                else:
                    text = data.decode("utf-8")
            except Exception as e:
                print(f"  Decompress error: {e}")
                continue

            rows, tfs = parse_gtrd_bulk(text, species)
            if rows:
                write_tsv(rows, output)
                stats.update(status="ok", edges=len(rows), tfs=len(tfs))
                return stats
            else:
                print(f"  No parseable rows from {url}")
                continue

    # Try API approach
    print(f"[GTRD] Trying API for {species}...")
    tf_list = try_gtrd_api_tf_list()
    if tf_list:
        print(f"  Found {len(tf_list)} TFs via API")
        stats["status"] = "api_partial"
    else:
        print(f"  GTRD API also unavailable for {species}")
        stats["status"] = "unavailable"

    return stats


def parse_gtrd_bulk(text: str, species: str) -> tuple[list[dict], set[str]]:
    rows = []
    tfs = set()
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for record in reader:
        tf = record.get("TF", record.get("tf_symbol", record.get("transcription_factor", "")))
        target = record.get("Target", record.get("target_gene", record.get("gene_symbol", "")))
        if not tf or not target:
            continue
        tfs.add(tf)
        rows.append({
            "tf_symbol": tf.strip(),
            "target_id": target.strip(),
            "source": "GTRD",
            "accession": record.get("experiment_id", record.get("ID", "")),
            "confidence": "0.60",
        })
    return rows, tfs


def write_tsv(rows: list[dict], output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["tf_symbol", "target_id", "source", "accession", "confidence"],
                           delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"  Wrote {len(rows)} rows to {output}")


def main():
    parser = argparse.ArgumentParser(description="Fetch GTRD TF-target edges")
    parser.add_argument("species", nargs="*", default=["human", "mouse"])
    args = parser.parse_args()

    results = {}
    for sp in args.species:
        out = DATA_DIR / f"gtrd_{sp}.tsv"
        results[sp] = fetch_species(sp, out)

    print(f"\n=== GTRD Results ===")
    print(json.dumps(results, indent=2))
    return 0 if any(r["status"] == "ok" for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
