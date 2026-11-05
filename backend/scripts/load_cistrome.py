#!/usr/bin/env python3
"""Load TF binding data from Cistrome DB.

Cistrome DB (cistrome.org/db) curates ChIP-seq and DNase-seq datasets for
human and mouse transcription factors. This script loads TF-target gene
associations from the Cistrome DB API.

The API has migrated from dc2.cistrome.org to db3.cistrome.org — this script
tries both versions and falls back gracefully.

Usage:
    python backend/scripts/load_cistrome.py --db backend/data/grn.sqlite3
    python backend/scripts/load_cistrome.py --probe-only
    python backend/scripts/load_cistrome.py --species human
"""
from __future__ import annotations

import argparse
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
SOURCE_NAME = "Cistrome"
SOURCE_VERSION = "DB3-2024"

API_HOSTS = [
    "https://db3.cistrome.org",
    "http://dc2.cistrome.org",
]

API_ENDPOINTS = {
    "filter": "/api/main_filter_bindct",
    "inspector": "/api/inspector",
    "batch_bindct": "/api/batch_bindct",
}

SPECIES_PARAMS = {
    "human": {"species": "Homo sapiens", "TF": "true"},
    "mouse": {"species": "Mus musculus", "TF": "true"},
}

HEADERS = {"User-Agent": "grn-atlas/1.0 (research)"}


def fetch_json(url: str, timeout: int = 30) -> dict | list | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            if "Page not found" in data or "Error 404" in data:
                return None
            return json.loads(data)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"  FAILED: {url} -> {e}")
        return None
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"  FAILED: {url} -> {e}")
        return None


def probe_endpoints() -> dict:
    results = {}
    for host in API_HOSTS:
        for name, path in API_ENDPOINTS.items():
            url = f"{host}{path}"
            if name == "filter":
                url += "?TF=true&species=Homo+sapiens"
            elif name == "inspector":
                url += "?id=1"
            label = f"{host.split('//')[1]}:{name}"
            print(f"  Probing {label}...", flush=True)
            data = fetch_json(url, timeout=15)
            if data is not None:
                if isinstance(data, list):
                    results[label] = {"url": url, "status": "OK", "count": len(data)}
                    print(f"    -> OK ({len(data)} records)")
                else:
                    results[label] = {"url": url, "status": "OK", "type": type(data).__name__}
                    print(f"    -> OK ({type(data).__name__})")
            else:
                results[label] = {"url": url, "status": "DOWN"}
                print(f"    -> DOWN")
            time.sleep(0.5)
    return results


def find_working_host() -> str | None:
    for host in API_HOSTS:
        url = f"{host}/api/main_filter_bindct?TF=true&species=Homo+sapiens"
        data = fetch_json(url, timeout=15)
        if data is not None and isinstance(data, list):
            print(f"  Using API host: {host}")
            return host
    return None


def fetch_tf_targets(host: str, sample_id: int) -> list[dict] | None:
    url = f"{host}/api/inspector?id={sample_id}"
    return fetch_json(url, timeout=30)


def load_species(
    conn: sqlite3.Connection, species: str, host: str,
    max_samples: int = 500, dry_run: bool = False,
) -> dict:
    stats = Counter()
    resolve = gene_resolver(conn, species)
    params = SPECIES_PARAMS[species]

    query = "&".join(f"{k}={v.replace(' ', '+')}" for k, v in params.items())
    url = f"{host}/api/main_filter_bindct?{query}"
    print(f"  Fetching sample index: {url}", flush=True)
    samples = fetch_json(url, timeout=60)
    if not samples or not isinstance(samples, list):
        print(f"  No samples available for {species}")
        return dict(stats)

    stats["total_samples"] = len(samples)
    print(f"  Found {len(samples)} TF ChIP-seq samples")

    edges = []
    source_url = url
    samples_to_process = samples[:max_samples]

    for i, sample in enumerate(samples_to_process):
        sample_id = sample.get("id") or sample.get("DCid")
        if not sample_id:
            continue
        tf_name = sample.get("factor") or sample.get("Factor") or ""
        tf_id = resolve(tf_name)
        if not tf_id:
            stats["tf_unmapped"] += 1
            continue

        stats["samples_processed"] += 1
        detail = fetch_tf_targets(host, sample_id)
        if not detail or not isinstance(detail, dict):
            stats["fetch_errors"] += 1
            time.sleep(0.5)
            continue

        targets = detail.get("genes", detail.get("targets", []))
        if isinstance(targets, list):
            for target_entry in targets:
                if isinstance(target_entry, str):
                    target_name = target_entry
                    score = None
                elif isinstance(target_entry, dict):
                    target_name = target_entry.get("gene", target_entry.get("symbol", ""))
                    score = target_entry.get("score")
                else:
                    continue

                target_id = resolve(target_name)
                if not target_id or target_id == tf_id:
                    stats["target_unmapped"] += 1
                    continue

                stats["edges_found"] += 1
                edges.append({
                    "species": species,
                    "source_id": tf_id,
                    "target_id": target_id,
                    "relation_type": "regulation",
                    "evidence_layer": "direct_unsigned",
                    "directness": "direct",
                    "record_key": f"Cistrome:{sample_id}:{tf_id}:{target_id}",
                    "confidence": float(score) if score else None,
                    "context": {
                        "sample_id": sample_id,
                        "factor": tf_name,
                        "assay": "ChIP-seq",
                    },
                })

        if (i + 1) % 50 == 0:
            print(f"    Processed {i + 1}/{len(samples_to_process)} samples, "
                  f"{len(edges)} edges so far", flush=True)
        time.sleep(0.3)

    seen = set()
    deduped = []
    for e in edges:
        key = (e["source_id"], e["target_id"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    stats["unique_edges"] = len(deduped)
    stats["duplicate_edges"] = len(edges) - len(deduped)

    if deduped and not dry_run:
        import_run_id = begin_import(
            conn, SOURCE_NAME, SOURCE_VERSION, source_url, None)
        stored = replace_source_evidence(
            conn, SOURCE_NAME, SOURCE_VERSION, import_run_id,
            deduped, species=[species])
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
                        help="Species to load (human, mouse, or all)")
    parser.add_argument("--max-samples", type=int, default=500,
                        help="Max ChIP-seq samples to process per species")
    args = parser.parse_args()

    print("=" * 60)
    print("Cistrome DB Regulatory Data Loader")
    print("=" * 60)

    if args.probe_only:
        results = probe_endpoints()
        available = sum(1 for v in results.values() if v["status"] == "OK")
        print(f"\n{available}/{len(results)} endpoints available")
        print(json.dumps(results, indent=2))
        return 0 if available > 0 else 1

    host = find_working_host()
    if not host:
        print("\nERROR: No working Cistrome DB API host found.")
        print("Both dc2.cistrome.org and db3.cistrome.org are unreachable.")
        print("Run with --probe-only to diagnose.")
        return 1

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    species_list = list(SPECIES_PARAMS.keys()) if args.species == "all" else [args.species]
    results = {}

    for species in species_list:
        print(f"\n{'=' * 60}")
        print(f"Loading Cistrome DB data for {species}")
        print(f"{'=' * 60}")
        results[species] = load_species(
            conn, species, host, max_samples=args.max_samples, dry_run=args.dry_run)
        print(f"  Result: {results[species]}")

    conn.close()
    print(f"\n{json.dumps(results, indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
