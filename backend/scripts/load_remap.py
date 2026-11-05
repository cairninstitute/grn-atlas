#!/usr/bin/env python3
"""Load ReMap 2022 ChIP-seq TF binding peaks as direct unsigned evidence.

Downloads the non-redundant (NR) BED file per genome, maps peaks to gene
promoters (TSS ± window), and stores TF→gene edges in regulatory_evidence.

ReMap 2022: https://remap.univ-amu.fr/
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import sqlite3
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import begin_import, finish_import, gene_resolver, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
SOURCE = "ReMap"
VERSION = "2022-v1.0"

NR_BEDS = {
    "human": {
        "url": "https://remap.univ-amu.fr/storage/remap2022/hg38/MACS2/remap2022_nr_macs2_hg38_v1_0.bed.gz",
        "genome": "hg38",
    },
    "mouse": {
        "url": "https://remap.univ-amu.fr/storage/remap2022/mm10/MACS2/remap2022_nr_macs2_mm10_v1_0.bed.gz",
        "genome": "mm10",
    },
    "arabidopsis": {
        "url": "https://remap.univ-amu.fr/storage/remap2022/tair10/tf/MACS2/remap2022_nr_macs2_TAIR10_v1_0.bed.gz",
        "genome": "TAIR10",
    },
}

CHROM_MAP = {
    "human": {f"chr{c}": str(c) for c in list(range(1, 23)) + ["X", "Y"]},
    "mouse": {f"chr{c}": str(c) for c in list(range(1, 20)) + ["X", "Y"]},
    "arabidopsis": {f"Chr{c}": str(c) for c in range(1, 6)},
}


def build_tss_index(conn: sqlite3.Connection, species: str,
                    window: int) -> dict[str, list[tuple[str, int]]]:
    """Build chromosome → [(gene_id, tss)] index for peak overlap."""
    index: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for row in conn.execute(
        "SELECT gene_id, chromosome, start, end, strand FROM gene_locations WHERE species=?",
        (species,),
    ):
        gene_id, chrom, start, end, strand = row
        tss = start if strand >= 0 else end
        index[str(chrom)].append((gene_id, tss))
    for chrom in index:
        index[chrom].sort(key=lambda x: x[1])
    return dict(index)


def find_genes_near_peak(tss_list: list[tuple[str, int]], peak_center: int,
                         window: int) -> list[str]:
    """Binary search for genes with TSS within window of peak center."""
    import bisect
    positions = [t[1] for t in tss_list]
    lo = bisect.bisect_left(positions, peak_center - window)
    hi = bisect.bisect_right(positions, peak_center + window)
    return [tss_list[i][0] for i in range(lo, hi)]


def process_species(conn: sqlite3.Connection, species: str, window: int,
                    max_targets_per_tf: int, cache_dir: Path) -> tuple[list[dict], Counter]:
    cfg = NR_BEDS.get(species)
    if not cfg:
        return [], Counter()

    stats = Counter()
    chrom_map = CHROM_MAP.get(species, {})
    resolve = gene_resolver(conn, species)
    tss_index = build_tss_index(conn, species, window)

    cache_file = cache_dir / f"remap_nr_{species}.bed.gz"
    if not cache_file.exists():
        print(f"  [{species}] Downloading ReMap NR BED (~{cfg['genome']})...", flush=True)
        req = urllib.request.Request(cfg["url"], headers={"User-Agent": "grn-atlas/1.0"})
        try:
            resp = urllib.request.urlopen(req, timeout=600)
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "wb") as f:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            print(f"  [{species}] Downloaded {cache_file.stat().st_size / 1e6:.1f} MB", flush=True)
        except Exception as e:
            print(f"  [{species}] Download failed: {e}", flush=True)
            cache_file.unlink(missing_ok=True)
            return [], Counter({"download_error": 1})
    else:
        print(f"  [{species}] Using cached {cache_file}", flush=True)

    edges: dict[str, dict[str, float]] = defaultdict(dict)

    with gzip.open(cache_file, "rt", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or line.startswith("track"):
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            stats["peaks"] += 1
            bed_chrom = parts[0]
            name_field = parts[3]
            tf_name = name_field.split(":")[0].split(".")[0]

            atlas_chrom = chrom_map.get(bed_chrom, bed_chrom.replace("chr", "").replace("Chr", ""))
            tss_list = tss_index.get(atlas_chrom)
            if not tss_list:
                stats["peaks_no_chrom"] += 1
                continue

            try:
                peak_center = (int(parts[1]) + int(parts[2])) // 2
            except ValueError:
                continue

            targets = find_genes_near_peak(tss_list, peak_center, window)
            if not targets:
                stats["peaks_no_gene"] += 1
                continue

            tf_id = resolve(tf_name)
            if not tf_id:
                stats["tf_unmapped"] += 1
                continue

            try:
                score = float(parts[4]) if len(parts) > 4 else 0.0
            except ValueError:
                score = 0.0

            for target_id in targets:
                if target_id == tf_id:
                    continue
                existing = edges[tf_id].get(target_id, 0.0)
                edges[tf_id][target_id] = max(existing, score)
                stats["peak_gene_links"] += 1

    evidence_rows = []
    for tf_id, targets in edges.items():
        sorted_targets = sorted(targets.items(), key=lambda x: -x[1])[:max_targets_per_tf]
        for target_id, score in sorted_targets:
            stats["edges"] += 1
            evidence_rows.append({
                "species": species,
                "source_id": tf_id,
                "target_id": target_id,
                "relation_type": "regulation",
                "evidence_layer": "direct_unsigned",
                "directness": "binding",
                "record_key": f"remap:{tf_id}:{target_id}:{species}",
                "confidence": min(0.85, 0.50 + 0.35 * (score / 1000.0)) if score > 0 else 0.55,
                "pmids": [],
            })

    print(f"  [{species}] {stats['peaks']} peaks → {stats['edges']} TF-target edges "
          f"({len(edges)} TFs)", flush=True)
    return evidence_rows, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", nargs="*", default=["human", "mouse", "arabidopsis"])
    parser.add_argument("--window", type=int, default=10000,
                        help="TSS ± window (bp) for peak-to-gene mapping")
    parser.add_argument("--max-targets-per-tf", type=int, default=500)
    parser.add_argument("--cache-dir", type=Path,
                        default=BACKEND / "data" / "remap_cache")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    all_evidence = []
    all_stats = {}
    fetched_species = []

    for species in args.species:
        print(f"\n[{species}] Processing ReMap data...", flush=True)
        evidence_rows, stats = process_species(
            conn, species, args.window, args.max_targets_per_tf, args.cache_dir)
        if evidence_rows:
            all_evidence.extend(evidence_rows)
            fetched_species.append(species)
        all_stats[species] = dict(stats)

    if all_evidence:
        run_id = begin_import(conn, SOURCE, VERSION,
                              "https://remap.univ-amu.fr/", sha256=None)
        replace_source_evidence(conn, SOURCE, VERSION, run_id, all_evidence,
                                species=fetched_species)
        finish_import(conn, run_id, {k: v for s in all_stats.values() for k, v in s.items()})
        conn.commit()
        print(f"\n  Loaded {len(all_evidence)} total ReMap evidence rows", flush=True)

    conn.close()
    print(f"\n=== ReMap Results ===")
    print(json.dumps(all_stats, indent=2))


if __name__ == "__main__":
    main()
