#!/usr/bin/env python3
"""Fetch TF-target regulatory edges from PlantTFDB / PlantRegMap.

PlantTFDB (planttfdb.gao-lab.org) hosts TF family classifications and
PlantRegMap (plantregmap.gao-lab.org) hosts predicted regulatory edges.
This script tries both download and API approaches.

Outputs edges into the regulatory_evidence table via the external_evidence helpers.
"""

from __future__ import annotations

import argparse
import csv
import gzip
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

PLANTTFDB_TF_LISTS = {
    "arabidopsis": {
        "url": "https://planttfdb.gao-lab.org/download/TF_list/Ath_TF_list.txt.gz",
        "taxid": "3702",
    },
    "rice": {
        "url": "https://planttfdb.gao-lab.org/download/TF_list/Osa_TF_list.txt.gz",
        "taxid": "39947",
    },
    "tomato": {
        "url": "https://planttfdb.gao-lab.org/download/TF_list/Sly_TF_list.txt.gz",
        "taxid": "4081",
    },
}

PLANTREGMAP_REGULATION = {
    "arabidopsis": "https://plantregmap.gao-lab.org/download/regulation/3702_regulation_At.txt",
    "rice": "https://plantregmap.gao-lab.org/download/regulation/39947_regulation_Os.txt",
    "tomato": "https://plantregmap.gao-lab.org/download/regulation/4081_regulation_Sl.txt",
}

PLANTTFDB_REGULATION = {
    "arabidopsis": "https://planttfdb.gao-lab.org/download/binding_site_prediction/Ath_bindsite_prediction.txt.gz",
    "rice": "https://planttfdb.gao-lab.org/download/binding_site_prediction/Osa_bindsite_prediction.txt.gz",
    "tomato": "https://planttfdb.gao-lab.org/download/binding_site_prediction/Sly_bindsite_prediction.txt.gz",
}

SOURCE_NAME = "PlantTFDB"
SOURCE_VERSION = "5.0"


def fetch_url(url: str, timeout: int = 120) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read()
    except Exception as e:
        print(f"  FAILED: {url} -> {e}")
        return None


def fetch_tf_list(species: str) -> list[dict]:
    cfg = PLANTTFDB_TF_LISTS.get(species)
    if not cfg:
        return []

    print(f"  Fetching PlantTFDB TF list for {species}...", flush=True)
    data = fetch_url(cfg["url"])
    if not data:
        return []

    try:
        text = gzip.decompress(data).decode("utf-8")
    except Exception:
        text = data.decode("utf-8", errors="replace")

    tfs = []
    for line in text.strip().splitlines():
        if line.startswith("#") or line.startswith("TF_ID"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            tfs.append({
                "gene_id": parts[0].strip(),
                "family": parts[1].strip() if len(parts) > 1 else "",
                "description": parts[2].strip() if len(parts) > 2 else "",
            })

    print(f"    Got {len(tfs)} TFs for {species}", flush=True)
    return tfs


def fetch_regulation_edges(species: str) -> list[dict]:
    edges = []

    # Try PlantRegMap first (better edge data)
    url = PLANTREGMAP_REGULATION.get(species)
    if url:
        print(f"  Trying PlantRegMap regulation for {species}...", flush=True)
        data = fetch_url(url)
        if data:
            text = data.decode("utf-8", errors="replace")
            parsed = parse_regulation_file(text, species)
            if parsed:
                print(f"    Got {len(parsed)} edges from PlantRegMap", flush=True)
                return parsed

    # Fall back to PlantTFDB binding site predictions
    url = PLANTTFDB_REGULATION.get(species)
    if url:
        print(f"  Trying PlantTFDB binding predictions for {species}...", flush=True)
        data = fetch_url(url)
        if data:
            try:
                text = gzip.decompress(data).decode("utf-8")
            except Exception:
                text = data.decode("utf-8", errors="replace")
            parsed = parse_binding_predictions(text, species)
            if parsed:
                print(f"    Got {len(parsed)} edges from PlantTFDB predictions", flush=True)
                return parsed

    print(f"  No regulation edges available for {species}", flush=True)
    return []


def parse_regulation_file(text: str, species: str) -> list[dict]:
    edges = []
    seen = set()
    for line in text.strip().splitlines():
        if line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        tf = parts[0].strip()
        target = parts[1].strip()
        key = (tf, target)
        if key in seen:
            continue
        seen.add(key)
        edges.append({
            "tf_id": tf,
            "target_id": target,
            "evidence_type": parts[2].strip() if len(parts) > 2 else "predicted",
            "score": parts[3].strip() if len(parts) > 3 else "",
        })
    return edges


def parse_binding_predictions(text: str, species: str) -> list[dict]:
    edges = []
    seen = set()
    for line in text.strip().splitlines():
        if line.startswith("#") or line.startswith("TF"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        tf = parts[0].strip()
        target = parts[1].strip()
        key = (tf, target)
        if key in seen:
            continue
        seen.add(key)
        edges.append({
            "tf_id": tf,
            "target_id": target,
            "evidence_type": "binding_prediction",
            "score": parts[2].strip() if len(parts) > 2 else "",
        })
    return edges


def resolve_edges(edges: list[dict], species: str, conn: sqlite3.Connection) -> tuple[list[dict], Counter]:
    stats = Counter()
    resolve = gene_resolver(conn, species)
    evidence_rows = []
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
        evidence_rows.append({
            "species": species,
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": "regulation",
            "evidence_layer": "direct_unsigned",
            "record_key": f"planttfdb:{edge['tf_id']}:{edge['target_id']}:{species}",
            "confidence": 0.55,
            "pmids": [],
        })
    return evidence_rows, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", nargs="*", default=["arabidopsis", "rice", "tomato"])
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    all_stats = {}
    all_evidence = []
    combined_stats = Counter()

    for species in args.species:
        print(f"\n[{species}] Fetching PlantTFDB data...", flush=True)

        tfs = fetch_tf_list(species)
        if tfs:
            all_stats[f"{species}_tfs"] = len(tfs)

        edges = fetch_regulation_edges(species)
        if edges:
            evidence_rows, stats = resolve_edges(edges, species, conn)
            all_evidence.extend(evidence_rows)
            combined_stats += stats
            all_stats[f"{species}_edges"] = dict(stats)
            print(f"  [{species}] Resolved: {dict(stats)}", flush=True)
        else:
            all_stats[f"{species}_edges"] = {"status": "no_data"}

        time.sleep(2)

    if all_evidence:
        run_id = begin_import(conn, SOURCE_NAME, SOURCE_VERSION,
                              "https://planttfdb.gao-lab.org", sha256=None)
        replace_source_evidence(conn, SOURCE_NAME, SOURCE_VERSION, run_id, all_evidence)
        finish_import(conn, run_id, dict(combined_stats))
        conn.commit()
        print(f"  Loaded {len(all_evidence)} total evidence rows", flush=True)

    conn.close()
    print(f"\n=== PlantTFDB Results ===")
    print(json.dumps(all_stats, indent=2))


if __name__ == "__main__":
    main()
