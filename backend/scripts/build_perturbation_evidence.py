#!/usr/bin/env python3
"""Aggregate perturbation experiments into conflict-aware signed evidence.

Novel pairs are retained only when direct binding independently supports the pair or
when at least two experiments agree. Individual observations remain untouched.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from external_evidence import begin_import, finish_import, replace_source_evidence  # noqa: E402
from perturbation_evidence import ensure_schema, perturbation_orientation  # noqa: E402


DB = BACKEND / "data" / "grn.sqlite3"
SOURCE = "Perturbation sign consensus"
VERSION = "consensus-v1"
MIN_ABS_EFFECT = 1.0
MIN_CONSISTENCY = 0.75


def _experiment_id(row: sqlite3.Row) -> str:
    if row[7]:
        return str(row[7])
    try:
        metadata = json.loads(row[6] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return str(
        metadata.get("sample_id") or metadata.get("experiment")
        or metadata.get("accession") or row[5] or f"observation:{row[0]}"
    )


def _context(row: sqlite3.Row) -> dict:
    try:
        metadata = json.loads(row[6] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    values = {
        "tissue": row[8] or metadata.get("tissue") or metadata.get("organism_part"),
        "treatment": row[9] or metadata.get("treatment"),
        "timepoint": row[10] or metadata.get("timepoint"),
        "genotype": row[11] or metadata.get("genotype"),
    }
    return {key: value for key, value in values.items() if value}


def _confidence(
    experiment_count: int,
    dataset_count: int,
    consistency: float,
    mean_abs_effect: float,
    has_binding: bool,
) -> float:
    score = 0.42
    score += 0.14 if has_binding else 0.0
    score += 0.08 * min(experiment_count, 3) / 3
    score += 0.14 * consistency
    score += 0.10 * min(mean_abs_effect, 3.0) / 3.0
    score += 0.05 if dataset_count > 1 else 0.0
    return round(min(0.93, score), 4)


def build(conn: sqlite3.Connection, species: str | None = None) -> dict:
    ensure_schema(conn)
    conn.row_factory = sqlite3.Row
    binding: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in conn.execute(
        "SELECT species,source_id,target_id,source_name FROM regulatory_evidence "
        "WHERE evidence_layer='direct_unsigned' OR directness IN ('binding','direct')"
    ):
        binding[(row[0], row[1], row[2])].add(row[3])

    if species:
        conn.execute("DELETE FROM perturbation_sign_consensus WHERE species=?", (species,))
    else:
        conn.execute("DELETE FROM perturbation_sign_consensus")

    where = (
        "WHERE observed_significant=1 AND observed_log2fc IS NOT NULL "
        "AND COALESCE(dataset_label,'') <> 'literature_curated' AND species=?" if species else
        "WHERE observed_significant=1 AND observed_log2fc IS NOT NULL "
        "AND COALESCE(dataset_label,'') <> 'literature_curated'"
    )
    query = (
        "SELECT obs_id,species,perturbed_gene,affected_gene,observed_log2fc,dataset_label,"
        "metadata,experiment_id,tissue,treatment,timepoint,genotype,perturbation_type "
        f"FROM perturbation_observations {where} "
        "ORDER BY species,perturbed_gene,affected_gene,obs_id"
    )
    cursor = conn.execute(query, (species,) if species else ())
    stats = Counter()
    consensus_rows = []
    evidence_rows = []
    current_key = None
    grouped_rows: list[sqlite3.Row] = []
    generated_at = datetime.now(timezone.utc).isoformat()

    def flush() -> None:
        nonlocal grouped_rows
        if not grouped_rows:
            return
        first = grouped_rows[0]
        key = (first[1], first[2], first[3])
        experiment_scores: dict[str, list[float]] = defaultdict(list)
        datasets = set()
        contexts = []
        for row in grouped_rows:
            orientation = perturbation_orientation(row[12])
            if orientation is None:
                stats["unknown_orientation_observations"] += 1
                continue
            experiment_scores[_experiment_id(row)].append(orientation * float(row[4]))
            if row[5]:
                datasets.add(str(row[5]))
            context = _context(row)
            if context and context not in contexts and len(contexts) < 12:
                contexts.append(context)
        scores = [statistics.mean(values) for values in experiment_scores.values()]
        if not scores:
            stats["unknown_orientation_pairs"] += 1
            grouped_rows = []
            return
        mean_score = statistics.mean(scores)
        mean_abs_effect = statistics.mean(abs(value) for value in scores)
        positive = sum(value > 0 for value in scores)
        negative = sum(value < 0 for value in scores)
        consistency = max(positive, negative) / max(positive + negative, 1)
        relation = "activation" if mean_score > 0 else "repression"
        binding_sources = sorted(binding.get(key, set()))
        has_binding = bool(binding_sources)
        status = "accepted"
        if consistency < MIN_CONSISTENCY:
            status = "sign_conflict"
        elif abs(mean_score) < MIN_ABS_EFFECT:
            status = "weak_effect"
        elif not has_binding and len(scores) < 2:
            status = "unreplicated_perturbation_only"
        confidence = _confidence(
            len(scores), len(datasets), consistency, mean_abs_effect, has_binding,
        )
        record = (
            *key, relation, mean_score, mean_abs_effect, consistency, len(grouped_rows),
            len(scores), len(datasets), json.dumps(sorted(datasets)),
            json.dumps(sorted(experiment_scores)[:100]), json.dumps(contexts, sort_keys=True),
            json.dumps(binding_sources), status, confidence, VERSION, generated_at,
        )
        if status == "accepted" or status == "sign_conflict":
            consensus_rows.append(record)
        stats[status] += 1
        stats["pairs_seen"] += 1
        if status == "accepted":
            evidence_rows.append({
                "species": key[0], "source_id": key[1], "target_id": key[2],
                "relation_type": relation, "evidence_layer": "perturbation_signed",
                "directness": "downstream", "record_key": "|".join(key),
                "confidence": confidence, "context": {"contexts": contexts},
                "pmids": [],
                "metadata": {
                    "model_version": VERSION,
                    "mean_activation_score": round(mean_score, 6),
                    "mean_abs_effect": round(mean_abs_effect, 6),
                    "sign_consistency": round(consistency, 6),
                    "observation_count": len(grouped_rows),
                    "experiment_count": len(scores),
                    "datasets": sorted(datasets),
                    "direct_binding_sources": binding_sources,
                },
            })
            stats["accepted_with_binding" if has_binding else "accepted_replicated_only"] += 1
        if len(consensus_rows) >= 20_000:
            conn.executemany(
                "INSERT INTO perturbation_sign_consensus VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                consensus_rows,
            )
            consensus_rows.clear()
        grouped_rows = []

    for row in cursor:
        key = (row[1], row[2], row[3])
        if current_key is not None and key != current_key:
            flush()
        current_key = key
        grouped_rows.append(row)
    flush()
    if consensus_rows:
        conn.executemany(
            "INSERT INTO perturbation_sign_consensus VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            consensus_rows,
        )

    run_id = begin_import(conn, SOURCE, VERSION, "derived:perturbation_observations", None)
    stats["evidence_stored"] = replace_source_evidence(
        conn, SOURCE, VERSION, run_id, evidence_rows,
    )
    finish_import(conn, run_id, dict(stats))
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species")
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        result = build(conn, args.species)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
