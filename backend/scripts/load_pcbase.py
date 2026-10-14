#!/usr/bin/env python3
"""Load reviewed PCBase peak files as direct unsigned TF occupancy evidence.

Every manifest row must assert coordinate compatibility or provide pre-lifted BED
coordinates. The loader refuses unknown assemblies rather than joining by chromosome
name alone.
"""

from __future__ import annotations

import argparse
import bisect
import io
import json
import sqlite3
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import begin_import, finish_import, gene_resolver, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
URL = "https://pcbase.itps.ncku.edu.tw/pcbase2/download_file.php"
SOURCE = "PCBase 2.0"
VERSION = "2.0-reviewed-assemblies"


def normalize_chromosome(value: str) -> str:
    value = value.strip()
    return value[3:] if value.lower().startswith("chr") else value


def promoter_index(conn: sqlite3.Connection, species: str, flank: int):
    by_chrom = defaultdict(list)
    for gene_id, chrom, start, end, strand in conn.execute(
        "SELECT gl.gene_id,gl.chromosome,gl.start,gl.end,gl.strand FROM gene_locations gl "
        "JOIN genes g ON g.id=gl.gene_id WHERE g.species=?", (species,),
    ):
        tss = start if strand >= 0 else end
        by_chrom[normalize_chromosome(str(chrom))].append(
            (max(0, tss - flank), tss + flank, gene_id)
        )
    return {chrom: (sorted(rows), [row[0] for row in sorted(rows)]) for chrom, rows in by_chrom.items()}


def download_bed(run: str, remote_species: str) -> str:
    data = urllib.parse.urlencode({"file": run, "type": "bed", "species": remote_species}).encode()
    request = urllib.request.Request(URL, data=data, headers={"User-Agent": "grn-atlas/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read().decode("utf-8", "replace")


def load(conn: sqlite3.Connection, manifest_path: Path, flank: int) -> dict:
    manifest = json.loads(manifest_path.read_text())
    rows_by_key, stats = {}, Counter()
    indices = {}
    for dataset in manifest.get("datasets", []):
        if dataset.get("review_status") != "approved" or not dataset.get("assembly_compatible"):
            stats["blocked_or_unreviewed"] += 1
            continue
        species = dataset["species"]
        resolve = gene_resolver(conn, species)
        tf_id = resolve(dataset.get("atlas_tf_id") or dataset["factor"])
        if not tf_id:
            stats["unmapped_tf"] += 1
            continue
        indices.setdefault(species, promoter_index(conn, species, flank))
        index = indices[species]
        for run in dataset["runs"]:
            bed = download_bed(run, dataset["remote_species"])
            for line in io.StringIO(bed):
                fields = line.rstrip().split("\t")
                if len(fields) < 3:
                    continue
                chrom = normalize_chromosome(fields[0])
                if chrom not in index:
                    continue
                start, end = int(fields[1]), int(fields[2])
                records, starts = index[chrom]
                first = bisect.bisect_left(starts, max(0, start - 2 * flank))
                stop = bisect.bisect_right(starts, end)
                for promoter_start, promoter_end, target_id in records[first:stop]:
                    if promoter_end < start or target_id == tf_id:
                        continue
                    key = f"{tf_id}|{target_id}|{run}"
                    rows_by_key[key] = {
                        "species": species, "source_id": tf_id, "target_id": target_id,
                        "relation_type": "regulation", "evidence_layer": "direct_unsigned",
                        "directness": "binding", "record_key": key, "confidence": 0.7,
                        "context": {"assembly": dataset["atlas_assembly"], "promoter_flank": flank},
                        "metadata": {"factor": dataset["factor"], "run": run,
                                     "source_assembly": dataset["source_assembly"]},
                    }
            stats["runs_loaded"] += 1
    run_id = begin_import(conn, SOURCE, VERSION, URL, None)
    stats["stored"] = replace_source_evidence(conn, SOURCE, VERSION, run_id, rows_by_key.values())
    finish_import(conn, run_id, dict(stats))
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--promoter-flank", type=int, default=1000)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        result = load(conn, args.manifest, args.promoter_flank)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
