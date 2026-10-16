#!/usr/bin/env python3
"""Import manually reviewed Expression Atlas contrasts from a JSON manifest.

The manifest is the review boundary. Each entry names the perturbed regulator,
perturbation direction, result file/URL, and exact result columns. This avoids
guessing causal direction from experiment titles.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import urllib.request
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import begin_import, finish_import, gene_resolver, replace_source_evidence  # noqa: E402
from perturbation_evidence import ensure_schema as ensure_perturbation_schema  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
SOURCE = "Expression Atlas reviewed perturbations"
VERSION = "manifest-v1"


def read_text(location: str, manifest_dir: Path) -> str:
    if location.startswith(("http://", "https://")):
        request = urllib.request.Request(location, headers={"User-Agent": "grn-atlas/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read().decode("utf-8", "replace")
    return (manifest_dir / location).read_text()


def relation_for(log2fc: float, perturbation_type: str) -> str:
    gain = any(token in perturbation_type.lower() for token in ("overexpress", "induc", "activation", "gain"))
    activating = log2fc > 0 if gain else log2fc < 0
    return "activation" if activating else "repression"


def load(conn: sqlite3.Connection, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    evidence_rows, observations, stats = [], [], Counter()
    for contrast in manifest.get("contrasts", []):
        if contrast.get("review_status") != "approved":
            stats["not_approved"] += 1
            continue
        species = contrast["species"]
        resolve = gene_resolver(conn, species)
        perturbed = resolve(contrast["perturbed_gene"])
        if not perturbed:
            stats["unmapped_regulator"] += 1
            continue
        columns = contrast["columns"]
        text = read_text(contrast["results"], manifest_path.parent)
        reader = csv.DictReader(io.StringIO(text), delimiter=contrast.get("delimiter", "\t"))
        label = f"ExpressionAtlas:{contrast['accession']}:{contrast['contrast']}"
        for record in reader:
            stats["input"] += 1
            target = resolve(record.get(columns["gene"]))
            if not target or target == perturbed:
                stats["unmapped_or_self"] += 1
                continue
            p_column = columns.get("p_value") or columns.get("adjusted_p")
            try:
                log2fc = float(record[columns["log2fc"]])
                p_value = float(record[p_column])
            except (KeyError, TypeError, ValueError):
                stats["invalid_result"] += 1
                continue
            max_p = float(contrast.get("max_p_value", contrast.get("max_adjusted_p", 0.05)))
            significant = p_value <= max_p and abs(log2fc) >= float(contrast.get("min_abs_log2fc", 0.5))
            observations.append((species, perturbed, contrast["perturbation_type"], target,
                                 log2fc, int(significant), label,
                                 json.dumps({"accession": contrast["accession"], "contrast": contrast["contrast"],
                                             "p_value": p_value,
                                             "p_value_type": contrast.get("p_value_type", "adjusted"),
                                             "reviewed": True}, sort_keys=True)))
            if significant:
                relation = relation_for(log2fc, contrast["perturbation_type"])
                evidence_rows.append({
                    "species": species, "source_id": perturbed, "target_id": target,
                    "relation_type": relation, "evidence_layer": "perturbation_signed",
                    "directness": "downstream", "record_key": f"{label}|{target}|{relation}",
                    "confidence": min(0.85, 0.55 + min(abs(log2fc), 3.0) / 10.0),
                    "context": contrast.get("context", {}),
                    "pmids": contrast.get("pmids", []),
                    "metadata": {"accession": contrast["accession"], "contrast": contrast["contrast"],
                                 "log2fc": log2fc, "p_value": p_value,
                                 "p_value_type": contrast.get("p_value_type", "adjusted"),
                                 "perturbation_type": contrast["perturbation_type"]},
                })
        stats["contrasts_loaded"] += 1
    ensure_perturbation_schema(conn)
    conn.execute("DELETE FROM perturbation_observations WHERE dataset_label LIKE 'ExpressionAtlas:%'")
    conn.executemany("INSERT INTO perturbation_observations (species,perturbed_gene,perturbation_type,affected_gene,observed_log2fc,observed_significant,dataset_label,metadata) VALUES (?,?,?,?,?,?,?,?)", observations)
    run_id = begin_import(conn, SOURCE, VERSION, "https://www.ebi.ac.uk/gxa/", None)
    stats["observations"] = len(observations)
    stats["stored"] = replace_source_evidence(conn, SOURCE, VERSION, run_id, evidence_rows)
    finish_import(conn, run_id, dict(stats))
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        result = load(conn, args.manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
