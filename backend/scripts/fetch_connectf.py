#!/usr/bin/env python3
"""Fetch TF-target binding edges from ConnecTF (connectf.org) for Arabidopsis.

ConnecTF aggregates ChIP-seq, DAP-seq, and TARGET experiment data for
Arabidopsis transcription factors. This script iterates over all TFs in
their API and collects TF→target edges with evidence metadata.

Output: backend/data/direct_binding/connectf_arabidopsis.tsv
Format: tf_symbol\ttarget_id\tsource\taccession\tconfidence

Usage:
    python backend/scripts/fetch_connectf.py [--output FILE] [--delay SECONDS]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

API_BASE = "https://connectf.org/api"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "direct_binding" / "connectf_arabidopsis.tsv"
AT_GENE_RE = re.compile(r"^AT[1-5CM]G\d{5}$")

EDGE_TYPE_CONFIDENCE = {
    "in planta:Bound": 0.80,
    "in planta:Regulated": 0.70,
    "in vitro:Bound:DAP": 0.60,
    "in vitro:Bound:ampDAP": 0.55,
}
DEFAULT_EDGE_CONFIDENCE = 0.50


def api_get(endpoint: str, params: dict | None = None, retries: int = 3) -> dict | list | None:
    url = f"{API_BASE}/{endpoint}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{qs}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (404, 500) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            if e.code in (404, 500):
                return None
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    return None


def fetch_tf_list() -> list[str]:
    data = api_get("tfs/")
    if not data:
        print("ERROR: Could not fetch TF list from ConnecTF", file=sys.stderr)
        sys.exit(1)
    return [t["value"] for t in data if AT_GENE_RE.match(t.get("value", ""))]


def edge_confidence(edge_type: str) -> float:
    for prefix, conf in EDGE_TYPE_CONFIDENCE.items():
        if edge_type.startswith(prefix):
            return conf
    return DEFAULT_EDGE_CONFIDENCE


def fetch_tf_targets(tf_id: str) -> list[dict]:
    data = api_get("overview/", {"tf": tf_id})
    if not data or "datasets" not in data:
        return []

    edges: dict[str, dict] = {}
    for ds in data["datasets"]:
        target_id = ds.get("gene_id", "").strip()
        if not target_id or not AT_GENE_RE.match(target_id):
            continue
        if target_id == tf_id:
            continue

        meta = ds.get("metadata", {})
        edge_type = meta.get("EDGE_TYPE", "unknown")
        doi = meta.get("DOI", "")
        pub = meta.get("DATA_SOURCE/PUBLICATION", "")

        key = f"{tf_id}|{target_id}"
        if key not in edges:
            edges[key] = {
                "tf_symbol": tf_id,
                "target_id": target_id,
                "edge_types": set(),
                "dois": set(),
                "pubs": set(),
                "confidence": 0.0,
                "n_datasets": 0,
            }
        e = edges[key]
        e["edge_types"].add(edge_type)
        if doi:
            e["dois"].add(doi)
        if pub:
            e["pubs"].add(pub)
        e["confidence"] = max(e["confidence"], edge_confidence(edge_type))
        e["n_datasets"] += 1

    return list(edges.values())


def main():
    parser = argparse.ArgumentParser(description="Fetch ConnecTF TF-target edges")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    parser.add_argument("--max-tfs", type=int, default=0, help="Limit TFs to fetch (0=all)")
    args = parser.parse_args()

    print("Fetching TF list from ConnecTF...")
    tfs = fetch_tf_list()
    print(f"  Found {len(tfs)} Arabidopsis TFs")

    if args.max_tfs > 0:
        tfs = tfs[: args.max_tfs]
        print(f"  Limited to first {args.max_tfs}")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    stats = Counter()
    all_edges: list[dict] = []

    for i, tf_id in enumerate(tfs, 1):
        edges = fetch_tf_targets(tf_id)
        stats["tfs_fetched"] += 1
        if edges:
            stats["tfs_with_data"] += 1
            stats["edges"] += len(edges)
            stats["datasets"] += sum(e["n_datasets"] for e in edges)
            all_edges.extend(edges)
        else:
            stats["tfs_empty"] += 1

        if i % 20 == 0 or i == len(tfs):
            print(f"  [{i}/{len(tfs)}] {tf_id} — {len(edges)} targets | cumulative: {stats['edges']} edges from {stats['datasets']} datasets")

        if i < len(tfs):
            time.sleep(args.delay)

    print(f"\nWriting {len(all_edges)} edges to {args.output}")

    with open(args.output, "w", newline="") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=["tf_symbol", "target_id", "source", "accession", "confidence"])
        writer.writeheader()
        for e in all_edges:
            source_parts = []
            for et in sorted(e["edge_types"]):
                if "DAP" in et:
                    source_parts.append("DAP-seq")
                elif "Bound" in et:
                    source_parts.append("ChIP-seq")
                elif "Regulated" in et:
                    source_parts.append("TARGET")
                else:
                    source_parts.append(et)
            source = "ConnecTF:" + "+".join(sorted(set(source_parts)))
            accession = ";".join(sorted(e["dois"])) if e["dois"] else ""
            writer.writerow({
                "tf_symbol": e["tf_symbol"],
                "target_id": e["target_id"],
                "source": source,
                "accession": accession,
                "confidence": f"{e['confidence']:.2f}",
            })

    print(f"\nSummary:")
    print(json.dumps(dict(stats), indent=2))


if __name__ == "__main__":
    main()
