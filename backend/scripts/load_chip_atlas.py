#!/usr/bin/env python3
"""Load bounded ChIP-Atlas TF occupancy as direct, unsigned evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import begin_import, finish_import, gene_resolver, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
INDEX_URL = "https://chip-atlas.org/data/target_genes_analysis.json"
BASE_URL = "https://chip-atlas.dbcls.jp/data/{genome}/target/{antigen}.1.tsv"
GENOMES = {"TAIR12": "arabidopsis", "hg38": "human", "mm10": "mouse"}
SOURCE = "ChIP-Atlas"
VERSION = "live-target-gene-index"


def fetch_text(url: str, max_lines: int | None = None, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "grn-atlas/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if max_lines is None:
            return response.read().decode("utf-8", "replace")
        lines = []
        for index, line in enumerate(response):
            if index >= max_lines:
                break
            lines.append(line.decode("utf-8", "replace"))
        return "".join(lines)


def parse_target_table(text: str, tf_id: str, resolve, species: str, antigen: str,
                       max_targets: int) -> tuple[list[dict], Counter]:
    stats = Counter()
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    header = next(reader, [])
    experiments = [column for column in header[2:-1] if "|" in column]
    rows_by_key = {}
    for rank, record in enumerate(reader, start=1):
        stats["input_targets"] += 1
        if rank > max_targets or len(record) < 2:
            continue
        target_id = resolve(record[0])
        if not target_id or target_id == tf_id:
            stats["unmapped_or_self"] += 1
            continue
        try:
            score = float(record[1])
        except ValueError:
            score = 0.0
        if score <= 0:
            continue
        record_key = f"{antigen}|1kb|{target_id}"
        candidate = {
            "species": species, "source_id": tf_id, "target_id": target_id,
            "relation_type": "regulation", "evidence_layer": "direct_unsigned",
            "directness": "binding", "record_key": record_key,
            "confidence": min(0.9, 0.45 + 0.45 / (1.0 + rank / 50.0)),
            "context": {"distance_from_tss_kb": 1, "experiments": len(experiments)},
            "metadata": {"antigen": antigen, "rank": rank, "average_score": score,
                         "experiment_accessions": experiments[:50]},
        }
        previous = rows_by_key.get(record_key)
        if previous is None or candidate["confidence"] > previous["confidence"]:
            rows_by_key[record_key] = candidate
        else:
            stats["alias_collisions"] += 1
    rows = list(rows_by_key.values())
    stats["mapped_targets"] = len(rows)
    return rows, stats


def load(conn: sqlite3.Connection, max_targets: int, workers: int = 12,
         request_timeout: int = 60) -> dict:
    index = json.loads(fetch_text(INDEX_URL))
    all_rows, stats = [], Counter()
    tasks = []
    seen_antigens = set()
    for genome, species in GENOMES.items():
        resolve = gene_resolver(conn, species)
        for antigen in index.get(genome, []):
            stats["antigens_available"] += 1
            antigen_key = (genome, antigen)
            if antigen_key in seen_antigens:
                stats["duplicate_antigens"] += 1
                continue
            seen_antigens.add(antigen_key)
            tf_id = resolve(antigen)
            if not tf_id:
                stats["antigens_unmapped"] += 1
                continue
            tasks.append((genome, species, antigen, tf_id, resolve))

    def fetch_one(task):
        genome, species, antigen, tf_id, resolve = task
        encoded = urllib.parse.quote(antigen, safe="")
        text = fetch_text(
            BASE_URL.format(genome=genome, antigen=encoded), max_targets + 1,
            timeout=request_timeout,
        )
        return parse_target_table(text, tf_id, resolve, species, antigen, max_targets)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(fetch_one, task) for task in tasks]
        for future in as_completed(futures):
            try:
                parsed, parsed_stats = future.result()
            except Exception:
                stats["tables_unavailable"] += 1
                continue
            all_rows.extend(parsed)
            stats.update(parsed_stats)
            stats["antigens_loaded"] += 1
    run_id = begin_import(conn, SOURCE, VERSION, INDEX_URL, None)
    stats["stored"] = replace_source_evidence(conn, SOURCE, VERSION, run_id, all_rows)
    finish_import(conn, run_id, dict(stats))
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--max-targets-per-tf", type=int, default=500)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--request-timeout", type=int, default=60)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        result = load(conn, args.max_targets_per_tf, args.workers, args.request_timeout)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
