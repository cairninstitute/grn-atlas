#!/usr/bin/env python3
"""Fetch TF data from GRASSIUS (Grass Regulatory Information Server).

GRASSIUS (grassius.org) provides curated TF and regulatory data for grass species
(maize, rice, sorghum, etc.). This script probes the site and attempts to download
TF family listings and any available regulatory edges.

Note: GRASSIUS primarily covers maize (Zea mays). Rice TFs overlap with PlantTFDB.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import begin_import, finish_import, gene_resolver, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"

GRASSIUS_URLS = {
    "tf_list": [
        "https://grassius.org/grasstfdb/tfomelist.csv",
        "https://grassius.org/download/grassius_tfs.csv",
        "https://grassius.org/tfomelist.php?species=Oryza+sativa",
    ],
    "rice_tfs": [
        "https://grassius.org/grasstfdb/family.php?species=Oryza+sativa&type=TF",
        "https://grassius.org/download/rice_tfs.csv",
    ],
    "regulation": [
        "https://grassius.org/grassregnet/download.php",
        "https://grassius.org/download/grassius_regulations.csv",
    ],
}

SOURCE_NAME = "GRASSIUS"
SOURCE_VERSION = "current"


def fetch_url(url: str, timeout: int = 60) -> tuple[str, bytes | None]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read()
        content_type = resp.headers.get("Content-Type", "")
        return content_type, data
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {url}")
        return "", None
    except Exception as e:
        print(f"  ERROR: {url} -> {e}")
        return "", None


def try_fetch_tf_list() -> list[dict]:
    """Try various URLs to get a GRASSIUS TF list."""
    for url in GRASSIUS_URLS["tf_list"] + GRASSIUS_URLS["rice_tfs"]:
        print(f"  Trying {url}...", flush=True)
        content_type, data = fetch_url(url)
        if data is None:
            time.sleep(1)
            continue

        text = data.decode("utf-8", errors="replace")

        # Check if it's HTML (not useful) or actual data
        if "<html" in text.lower()[:500]:
            # Try to parse HTML table
            tfs = parse_html_tf_table(text)
            if tfs:
                print(f"    Parsed {len(tfs)} TFs from HTML", flush=True)
                return tfs
            print(f"    Got HTML page, not parseable as TF list", flush=True)
            time.sleep(1)
            continue

        # Try CSV/TSV parsing
        tfs = parse_csv_tf_list(text)
        if tfs:
            print(f"    Got {len(tfs)} TFs", flush=True)
            return tfs

        time.sleep(1)

    return []


def parse_csv_tf_list(text: str) -> list[dict]:
    tfs = []
    for delim in ["\t", ","]:
        reader = csv.reader(io.StringIO(text), delimiter=delim)
        header = next(reader, [])
        if not header:
            continue
        # Look for gene ID column
        id_col = None
        family_col = None
        for i, h in enumerate(header):
            hl = h.lower().strip()
            if hl in ("gene_id", "geneid", "id", "locus", "gene"):
                id_col = i
            if hl in ("family", "tf_family", "class"):
                family_col = i
        if id_col is None:
            continue
        for row in reader:
            if len(row) > id_col:
                tfs.append({
                    "gene_id": row[id_col].strip(),
                    "family": row[family_col].strip() if family_col and len(row) > family_col else "",
                })
        if tfs:
            return tfs
    return []


def parse_html_tf_table(html: str) -> list[dict]:
    """Very basic HTML table parser for GRASSIUS pages."""
    tfs = []
    import re
    # Find table rows with gene IDs (rice: LOC_Os pattern)
    for match in re.finditer(r'(LOC_Os\d+g\d+)', html):
        gene_id = match.group(1)
        if gene_id not in {t["gene_id"] for t in tfs}:
            tfs.append({"gene_id": gene_id, "family": ""})
    return tfs


def try_fetch_regulations() -> list[dict]:
    """Try to fetch regulatory edges from GRASSIUS."""
    for url in GRASSIUS_URLS["regulation"]:
        print(f"  Trying regulation data: {url}...", flush=True)
        content_type, data = fetch_url(url)
        if data is None:
            time.sleep(1)
            continue

        text = data.decode("utf-8", errors="replace")
        if "<html" in text.lower()[:500]:
            print(f"    Got HTML, not data file", flush=True)
            time.sleep(1)
            continue

        edges = parse_regulation_csv(text)
        if edges:
            return edges

        time.sleep(1)

    return []


def parse_regulation_csv(text: str) -> list[dict]:
    edges = []
    for delim in ["\t", ","]:
        reader = csv.reader(io.StringIO(text), delimiter=delim)
        header = next(reader, [])
        if len(header) < 2:
            continue
        for row in reader:
            if len(row) >= 2:
                edges.append({
                    "tf_id": row[0].strip(),
                    "target_id": row[1].strip(),
                    "evidence": row[2].strip() if len(row) > 2 else "",
                })
    return edges if len(edges) > 10 else []


def load_edges(edges: list[dict], conn: sqlite3.Connection) -> Counter:
    stats = Counter()
    resolve = gene_resolver(conn, "rice")

    run_id = begin_import(conn, SOURCE_NAME, SOURCE_VERSION, "https://grassius.org")

    for edge in edges:
        stats["input"] += 1
        source_id = resolve(edge["tf_id"])
        target_id = resolve(edge["target_id"])
        if not source_id or not target_id:
            stats["unresolved"] += 1
            continue
        if source_id == target_id:
            stats["self_loop"] += 1
            continue

        stats["resolved"] += 1
        replace_source_evidence(
            conn,
            species="rice",
            source_id=source_id,
            target_id=target_id,
            relation_type="regulation",
            evidence_layer="direct_unsigned",
            source_name=SOURCE_NAME,
            source_version=SOURCE_VERSION,
            record_key=f"grassius:{edge['tf_id']}:{edge['target_id']}",
            confidence=0.60,
            pmids=[],
            import_run_id=run_id,
        )

    finish_import(conn, run_id, dict(stats))
    conn.commit()
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    results = {}

    print("=== GRASSIUS TF Fetch ===", flush=True)

    # Fetch TF list
    tfs = try_fetch_tf_list()
    results["tfs_found"] = len(tfs)
    if tfs:
        print(f"  Found {len(tfs)} TFs", flush=True)
        # Sample
        for tf in tfs[:5]:
            print(f"    {tf}", flush=True)

    # Fetch regulatory edges
    edges = try_fetch_regulations()
    results["edges_found"] = len(edges)
    if edges:
        stats = load_edges(edges, conn)
        results["load_stats"] = dict(stats)
        print(f"  Loaded edges: {dict(stats)}", flush=True)
    else:
        print("  No regulatory edges available from GRASSIUS", flush=True)
        results["load_stats"] = {"status": "no_data"}

    conn.close()
    print(f"\n=== GRASSIUS Results ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
