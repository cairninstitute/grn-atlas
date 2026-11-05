#!/usr/bin/env python3
"""Load TF-target regulatory edges from GRASSIUS (Grass Regulatory Information Server).

GRASSIUS hosts curated TF classifications and regulatory interactions for grass
species (maize, rice, sorghum, sugarcane). Data is available via the web interface
at grassius.org — this script attempts multiple download strategies.

Currently loads: TF family annotations (to validate/enrich existing atlas TFs).
Regulatory edges are loaded when the download endpoint is available.

Usage:
    python backend/scripts/load_grassius.py --db backend/data/grn.sqlite3
    python backend/scripts/load_grassius.py --probe-only
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
SOURCE_NAME = "GRASSIUS"
SOURCE_VERSION = "2024"

GRASSIUS_BASE = "https://grassius.org"

SPECIES_MAP = {
    "Maize": "maize",
    "Rice": "rice",
    "Sorghum": "sorghum",
    "Sugarcane": "sugarcane",
}

TF_FAMILIES_URL = f"{GRASSIUS_BASE}/grasstfdb/tfdb_family_summary.php"

TF_LIST_URLS = {
    "rice": [
        f"{GRASSIUS_BASE}/grasstfdb/tf_browsefamily.php?species=Rice&family=all",
        f"{GRASSIUS_BASE}/data/rice_tf_list.txt",
    ],
    "maize": [
        f"{GRASSIUS_BASE}/grasstfdb/tf_browsefamily.php?species=Maize&family=all",
        f"{GRASSIUS_BASE}/data/maize_tf_list.txt",
    ],
}

REGULATION_URLS = {
    "rice": [
        f"{GRASSIUS_BASE}/data/rice_regulation.txt",
        f"{GRASSIUS_BASE}/grasstfdb/rice_interactions.txt",
    ],
    "maize": [
        f"{GRASSIUS_BASE}/data/maize_regulation.txt",
        f"{GRASSIUS_BASE}/grasstfdb/maize_interactions.txt",
    ],
}

HEADERS = {"User-Agent": "grn-atlas/1.0 (research; ken.janik@gmail.com)"}


def fetch_url(url: str, timeout: int = 30) -> bytes | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            text = data.decode("utf-8", errors="replace")
            if "Page not Found" in text or "404" in text[:500]:
                return None
            return data
    except Exception as e:
        print(f"  FAILED: {url} -> {e}")
        return None


def probe_endpoints() -> dict:
    results = {}
    urls_to_check = [
        ("home", f"{GRASSIUS_BASE}/"),
        ("tf_families", TF_FAMILIES_URL),
    ]
    for species, url_list in TF_LIST_URLS.items():
        for i, url in enumerate(url_list):
            urls_to_check.append((f"tf_list_{species}_{i}", url))
    for species, url_list in REGULATION_URLS.items():
        for i, url in enumerate(url_list):
            urls_to_check.append((f"regulation_{species}_{i}", url))

    for label, url in urls_to_check:
        print(f"  Probing {label}: {url}", flush=True)
        data = fetch_url(url, timeout=15)
        status = "OK" if data else "DOWN"
        size = len(data) if data else 0
        results[label] = {"url": url, "status": status, "size": size}
        print(f"    -> {status} ({size} bytes)")
        time.sleep(0.5)

    return results


def parse_tf_list(text: str) -> list[dict]:
    tfs = []
    for line in text.strip().splitlines():
        if line.startswith("#") or line.startswith("Gene") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            tfs.append({
                "gene_id": parts[0].strip(),
                "family": parts[1].strip() if len(parts) > 1 else "",
                "description": parts[2].strip() if len(parts) > 2 else "",
            })
    return tfs


def parse_regulation(text: str) -> list[dict]:
    edges = []
    seen = set()
    for line in text.strip().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        tf = parts[0].strip()
        target = parts[1].strip()
        key = (tf, target)
        if key in seen or tf == target:
            continue
        seen.add(key)
        evidence_type = parts[2].strip() if len(parts) > 2 else "curated"
        edges.append({
            "tf_id": tf,
            "target_id": target,
            "evidence_type": evidence_type,
        })
    return edges


def load_species(
    conn: sqlite3.Connection, species: str, dry_run: bool = False,
) -> dict:
    stats = Counter()
    resolve = gene_resolver(conn, species)

    for url in TF_LIST_URLS.get(species, []):
        print(f"  Trying TF list: {url}", flush=True)
        data = fetch_url(url)
        if data:
            tfs = parse_tf_list(data.decode("utf-8", errors="replace"))
            stats["tf_list_entries"] = len(tfs)
            mapped = sum(1 for tf in tfs if resolve(tf["gene_id"]))
            stats["tf_list_mapped"] = mapped
            print(f"    Got {len(tfs)} TFs, {mapped} mapped to atlas")
            break

    edges = []
    source_url = ""
    for url in REGULATION_URLS.get(species, []):
        print(f"  Trying regulation: {url}", flush=True)
        data = fetch_url(url)
        if data:
            raw_edges = parse_regulation(data.decode("utf-8", errors="replace"))
            source_url = url
            stats["input_edges"] = len(raw_edges)
            for e in raw_edges:
                src = resolve(e["tf_id"])
                tgt = resolve(e["target_id"])
                if src and tgt and src != tgt:
                    edges.append({
                        "species": species,
                        "source_id": src,
                        "target_id": tgt,
                        "relation_type": "regulation",
                        "evidence_layer": "direct_unsigned",
                        "directness": "direct",
                        "record_key": f"GRASSIUS:{src}:{tgt}",
                        "confidence": None,
                        "context": {"evidence_type": e["evidence_type"]},
                    })
                else:
                    stats["unmapped_or_self"] += 1
            break

    stats["resolved"] = len(edges)

    if edges and not dry_run:
        import_run_id = begin_import(
            conn, SOURCE_NAME, SOURCE_VERSION, source_url, None)
        stored = replace_source_evidence(
            conn, SOURCE_NAME, SOURCE_VERSION, import_run_id,
            edges, species=[species])
        stats["stored"] = stored
        finish_import(conn, import_run_id, dict(stats))

    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--probe-only", action="store_true",
                        help="Only check endpoint availability")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--species", default="all",
                        help="Species to load (rice, maize, or all)")
    args = parser.parse_args()

    print("=" * 60)
    print("GRASSIUS Regulatory Data Loader")
    print("=" * 60)

    if args.probe_only:
        results = probe_endpoints()
        available = sum(1 for v in results.values() if v["status"] == "OK")
        print(f"\n{available}/{len(results)} endpoints available")
        print(json.dumps(results, indent=2))
        return 0 if available > 0 else 1

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    species_list = ["rice", "maize"] if args.species == "all" else [args.species]
    results = {}

    for species in species_list:
        print(f"\n{'=' * 60}")
        print(f"Loading GRASSIUS data for {species}")
        print(f"{'=' * 60}")
        results[species] = load_species(conn, species, dry_run=args.dry_run)
        print(f"  Result: {results[species]}")

    conn.close()
    print(f"\n{json.dumps(results, indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
