#!/usr/bin/env python3
"""Normalize experiment-level ConnecTF binding and perturbation evidence."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from external_evidence import (  # noqa: E402
    begin_import, finish_import, gene_resolver, replace_source_evidence,
)

DB = BACKEND / "data" / "grn.sqlite3"
SOURCE = "ConnecTF experiment evidence"
VERSION = "release-v1"
URL = "https://connectf.s3.amazonaws.com/connectf_data_release_v1.tar.gz"
LOCUS_RE = re.compile(r"((?:AT[1-5CM]G\d{5})|(?:LOC_Os\d+g\d+))", re.IGNORECASE)


def parse_metadata(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(errors="replace").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.lstrip("*").strip().lower().replace("/", "_")] = value.strip()
    return values


def _column(header: list[str], *names: str) -> int | None:
    normalized = [value.strip().strip('"').lower() for value in header]
    for name in names:
        if name.lower() in normalized:
            return normalized.index(name.lower())
    return None


def perturbation_mode(path: Path, metadata: dict[str, str], species: str | None = None) -> str | None:
    text = " ".join((path.stem, metadata.get("genotype", ""),
                     metadata.get("edge_type", ""), metadata.get("treatments", ""))).lower()
    if any(token in text for token in ("_lof", " lof", "knockout", "knock-down", "knockdown", " mutant")):
        return "loss"
    if any(token in text for token in ("_gof", " gof", "_oe", "overexpress", "target", " dex")):
        return "gain"
    # Release-v1 Arabidopsis DESeq2 files are inducible TARGET gain-of-function assays;
    # the public archive omits metadata sidecars for most of these files.
    if species == "arabidopsis" and "deseq" in path.stem.lower():
        return "gain"
    return None


def load(conn: sqlite3.Connection, release: Path) -> dict:
    rows: list[dict] = []
    stats = Counter()
    for species, folder in (("arabidopsis", "arabidopsis"), ("rice", "rice")):
        data_dir = release / folder / "data"
        meta_dir = release / folder / "metadata"
        if not data_dir.is_dir():
            continue
        resolve = gene_resolver(conn, species)
        for path in sorted(data_dir.glob("*.csv")):
            if path.name.startswith("._"):
                continue
            metadata = parse_metadata(meta_dir / f"{path.stem}.txt")
            tf_label = metadata.get("transcription_factor_id")
            if not tf_label:
                match = LOCUS_RE.search(path.stem)
                tf_label = match.group(1) if match else None
            source_id = resolve(tf_label)
            if not source_id:
                stats["unmapped_experiments"] += 1
                continue
            with path.open(errors="replace", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                if not header:
                    continue
                fc_col = _column(header, "log2fc", "log2foldchange", "logfc")
                p_col = _column(header, "padj", "fdr", "qvalue", "p-value", "pvalue")
                edge_type = metadata.get("edge_type", "")
                experiment_type = metadata.get("experiment_type", "")
                is_binding = experiment_type.lower() == "binding" or "bound" in edge_type.lower()
                mode = perturbation_mode(path, metadata, species)
                for record_number, record in enumerate(reader, start=2):
                    if not record:
                        continue
                    target_id = resolve(record[0].strip().strip('"'))
                    if not target_id or target_id == source_id:
                        stats["unmapped_or_self"] += 1
                        continue
                    relation = "regulation"
                    layer = "direct_unsigned"
                    directness = "binding" if is_binding else "downstream"
                    confidence = 0.68 if is_binding else 0.55
                    log2fc = None
                    p_value = None
                    if fc_col is not None and fc_col < len(record):
                        try:
                            log2fc = float(record[fc_col])
                            p_value = float(record[p_col]) if p_col is not None and p_col < len(record) else None
                        except ValueError:
                            stats["invalid_statistics"] += 1
                            continue
                        if p_value is not None and p_value > 0.05:
                            stats["not_significant"] += 1
                            continue
                        if log2fc == 0:
                            continue
                        if mode is None:
                            stats["ambiguous_perturbation_direction"] += 1
                            continue
                        activating = log2fc > 0 if mode == "gain" else log2fc < 0
                        relation = "activation" if activating else "repression"
                        layer = "perturbation_signed"
                        confidence = min(0.78, 0.52 + min(abs(log2fc), 3.0) * 0.07)
                    elif not is_binding:
                        stats["unsigned_nonbinding"] += 1
                        continue
                    context = {
                        key: metadata.get(key) for key in (
                            "tissue_sample", "treatments", "control", "treatment_time",
                            "genotype", "growth_period_days", "growth_medium",
                        ) if metadata.get(key)
                    }
                    rows.append({
                        "species": species,
                        "source_id": source_id,
                        "target_id": target_id,
                        "relation_type": relation,
                        "evidence_layer": layer,
                        "directness": directness,
                        "record_key": f"{path.stem}|{record_number}|{target_id}",
                        "confidence": confidence,
                        "context": context,
                        "pmids": ["33631799"],
                        "metadata": {
                            "experiment": path.stem,
                            "experiment_type": experiment_type,
                            "edge_type": edge_type,
                            "method": metadata.get("technology_method"),
                            "analysis_method": metadata.get("analysis_method"),
                            "analysis_cutoff": metadata.get("analysis_cutoff"),
                            "log2fc": log2fc,
                            "p_value": p_value,
                            "perturbation_mode": mode,
                        },
                    })
                    stats[layer] += 1
    run_id = begin_import(conn, SOURCE, VERSION, URL, None)
    stats["stored"] = replace_source_evidence(conn, SOURCE, VERSION, run_id, rows)
    finish_import(conn, run_id, dict(stats))
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path, nargs="?", default=Path("/tmp/connectf_data_release_v1"))
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    if not args.release.is_dir():
        print(json.dumps({"skipped": "ConnecTF release unavailable", "path": str(args.release)}))
        return 0
    with sqlite3.connect(args.db) as conn:
        result = load(conn, args.release)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
