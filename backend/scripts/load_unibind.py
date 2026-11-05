#!/usr/bin/env python3
"""Load UniBind 2022 motif-validated ChIP-seq TF binding sites as evidence.

Downloads compressed TFBS BED files per genome, maps peaks to gene promoters
(TSS ± window), and stores TF→gene edges in regulatory_evidence.

UniBind provides high-confidence TF binding sites validated by both ChIP-seq
peaks AND matching motifs — higher specificity than ChIP-seq alone.

UniBind: https://unibind.uio.no/
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import begin_import, finish_import, gene_resolver, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
SOURCE = "UniBind"
VERSION = "2022-Robust"

TFBS_BEDS = {
    "human": {
        "url": "https://unibind.uio.no/static/data/20220914/bulk_Robust/Homo_sapiens/hg38_compressed_TFBSs.bed.gz",
        "genome": "hg38",
    },
    "mouse": {
        "url": "https://unibind.uio.no/static/data/20220914/bulk_Robust/Mus_musculus/mm10_compressed_TFBSs.bed.gz",
        "genome": "mm10",
    },
    "arabidopsis": {
        "url": "https://unibind.uio.no/static/data/20220914/bulk_Robust/Arabidopsis_thaliana/TAIR10_compressed_TFBSs.bed.gz",
        "genome": "TAIR10",
    },
}

CHROM_MAP = {
    "human": {f"chr{c}": str(c) for c in list(range(1, 23)) + ["X", "Y"]},
    "mouse": {f"chr{c}": str(c) for c in list(range(1, 20)) + ["X", "Y"]},
    "arabidopsis": {f"chr{c}": str(c) for c in range(1, 6)},
}

# Pattern: EXP_ID_tissue_TFname_motifID
TF_PATTERN = re.compile(r"^EXP\d+_.+?_([A-Za-z0-9]+(?:::|-\w+)?)_MA\d+")


def extract_tf_name(name_field: str) -> str | None:
    """Extract TF name from UniBind name field like EXP041276_tissue_AG_MA0005.2"""
    m = TF_PATTERN.match(name_field)
    if m:
        return m.group(1).replace("::", "")
    parts = name_field.split("_")
    if len(parts) >= 3:
        for i in range(len(parts) - 1, 0, -1):
            if parts[i].startswith("MA") and "." in parts[i]:
                return parts[i - 1]
    return None


def build_tss_index(conn: sqlite3.Connection, species: str) -> dict[str, list[tuple[str, int]]]:
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
    import bisect
    positions = [t[1] for t in tss_list]
    lo = bisect.bisect_left(positions, peak_center - window)
    hi = bisect.bisect_right(positions, peak_center + window)
    return [tss_list[i][0] for i in range(lo, hi)]


def process_species(conn: sqlite3.Connection, species: str, window: int,
                    max_targets_per_tf: int, cache_dir: Path) -> tuple[list[dict], Counter]:
    cfg = TFBS_BEDS.get(species)
    if not cfg:
        return [], Counter()

    stats = Counter()
    chrom_map = CHROM_MAP.get(species, {})
    resolve = gene_resolver(conn, species)
    tss_index = build_tss_index(conn, species)

    cache_file = cache_dir / f"unibind_{species}.bed.gz"
    if not cache_file.exists():
        print(f"  [{species}] Downloading UniBind TFBS BED...", flush=True)
        req = urllib.request.Request(cfg["url"], headers={"User-Agent": "grn-atlas/1.0"})
        try:
            resp = urllib.request.urlopen(req, timeout=900)
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

    edges: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    with gzip.open(cache_file, "rt", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or line.startswith("track"):
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            stats["sites"] += 1

            bed_chrom = parts[0]
            name_field = parts[3]
            tf_name = extract_tf_name(name_field)
            if not tf_name:
                stats["tf_parse_fail"] += 1
                continue

            atlas_chrom = chrom_map.get(bed_chrom, bed_chrom.replace("chr", "").replace("Chr", ""))
            tss_list = tss_index.get(atlas_chrom)
            if not tss_list:
                stats["sites_no_chrom"] += 1
                continue

            try:
                peak_center = (int(parts[1]) + int(parts[2])) // 2
            except ValueError:
                continue

            targets = find_genes_near_peak(tss_list, peak_center, window)
            if not targets:
                stats["sites_no_gene"] += 1
                continue

            tf_id = resolve(tf_name)
            if not tf_id:
                stats["tf_unmapped"] += 1
                continue

            for target_id in targets:
                if target_id == tf_id:
                    continue
                edges[tf_id][target_id] += 1
                stats["site_gene_links"] += 1

    evidence_rows = []
    for tf_id, targets in edges.items():
        sorted_targets = sorted(targets.items(), key=lambda x: -x[1])[:max_targets_per_tf]
        for target_id, hit_count in sorted_targets:
            stats["edges"] += 1
            evidence_rows.append({
                "species": species,
                "source_id": tf_id,
                "target_id": target_id,
                "relation_type": "regulation",
                "evidence_layer": "direct_unsigned",
                "directness": "binding",
                "record_key": f"unibind:{tf_id}:{target_id}:{species}",
                "confidence": min(0.90, 0.55 + 0.05 * min(hit_count, 7)),
                "pmids": [],
                "metadata": {"motif_validated_hits": hit_count},
            })

    print(f"  [{species}] {stats['sites']} sites → {stats['edges']} TF-target edges "
          f"({len(edges)} TFs)", flush=True)
    return evidence_rows, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", nargs="*", default=["human", "mouse", "arabidopsis"])
    parser.add_argument("--window", type=int, default=10000)
    parser.add_argument("--max-targets-per-tf", type=int, default=500)
    parser.add_argument("--cache-dir", type=Path,
                        default=BACKEND / "data" / "unibind_cache")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    all_evidence = []
    all_stats = {}
    fetched_species = []

    for species in args.species:
        print(f"\n[{species}] Processing UniBind data...", flush=True)
        evidence_rows, stats = process_species(
            conn, species, args.window, args.max_targets_per_tf, args.cache_dir)
        if evidence_rows:
            all_evidence.extend(evidence_rows)
            fetched_species.append(species)
        all_stats[species] = dict(stats)

    if all_evidence:
        run_id = begin_import(conn, SOURCE, VERSION,
                              "https://unibind.uio.no/", sha256=None)
        replace_source_evidence(conn, SOURCE, VERSION, run_id, all_evidence,
                                species=fetched_species)
        finish_import(conn, run_id, {k: v for s in all_stats.values() for k, v in s.items()})
        conn.commit()
        print(f"\n  Loaded {len(all_evidence)} total UniBind evidence rows", flush=True)

    conn.close()
    print(f"\n=== UniBind Results ===")
    print(json.dumps(all_stats, indent=2))


if __name__ == "__main__":
    main()
