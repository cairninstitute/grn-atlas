#!/usr/bin/env python3
"""Synthesize conflict-aware signed candidates from normalized evidence layers."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"


def build(conn: sqlite3.Connection) -> dict:
    conn.executescript("""
        DROP TABLE IF EXISTS regulatory_edge_candidates;
        CREATE TABLE IF NOT EXISTS regulatory_edge_candidates (
            species TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL, confidence REAL NOT NULL,
            support_class TEXT NOT NULL, evidence_sources TEXT NOT NULL,
            evidence_layers TEXT NOT NULL, status TEXT NOT NULL,
            evidence_tier TEXT NOT NULL DEFAULT 'supported',
            inclusion_probability REAL NOT NULL DEFAULT 0.5,
            metadata TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (species, source_id, target_id, relation_type)
        );
        CREATE INDEX IF NOT EXISTS idx_rec_species_status
            ON regulatory_edge_candidates(species, status, confidence);
    """)
    grouped = defaultdict(list)
    for row in conn.execute(
        "SELECT species,source_id,target_id,relation_type,evidence_layer,directness,"
        "source_name,COALESCE(confidence,0.6) FROM regulatory_evidence"
    ):
        grouped[(row[0], row[1], row[2])].append(row[3:])
    existing = {(row[0], row[1]): (row[2], row[3]) for row in conn.execute(
        "SELECT source_id,target_id,COALESCE(sign,regulation_type),confidence FROM interactions"
    )}
    calibrated_classes = set()
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='perturbation_sign_calibration'"
    ).fetchone():
        calibrated_classes = {
            (row[0], row[1]) for row in conn.execute(
                "SELECT species,relation_type FROM perturbation_sign_calibration WHERE gate_pass=1"
            )
        }
    consensus = {}
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='perturbation_sign_consensus'"
    ).fetchone():
        consensus = {
            (row[0], row[1], row[2]): {
                "mean_activation_score": round(float(row[3]), 6),
                "mean_abs_effect": round(float(row[4]), 6),
                "sign_consistency": round(float(row[5]), 6),
                "observation_count": int(row[6]),
                "experiment_count": int(row[7]),
                "dataset_count": int(row[8]),
                "datasets": json.loads(row[9]),
                "contexts": json.loads(row[10]),
                "model_version": row[11],
            }
            for row in conn.execute(
                "SELECT species,source_id,target_id,mean_activation_score,mean_abs_effect,"
                "sign_consistency,observation_count,experiment_count,dataset_count,datasets,"
                "contexts,model_version FROM perturbation_sign_consensus WHERE status='accepted'"
            )
        }
    output = []
    summary = defaultdict(int)
    for (species, source_id, target_id), records in grouped.items():
        consensus_present = any(
            record[3] == "Perturbation sign consensus" for record in records
        )
        if consensus_present:
            # Individual experiments remain queryable, but the versioned consensus is
            # the only perturbation row allowed to make a global candidate sign call.
            records = [
                record for record in records
                if record[1] != "perturbation_signed"
                or record[3] == "Perturbation sign consensus"
            ]
        signed = defaultdict(list)
        binding_sources = set()
        layers = set()
        for relation, layer, directness, source_name, confidence in records:
            layers.add(layer)
            if relation in ("activation", "repression"):
                signed[relation].append((source_name, float(confidence), layer, directness))
            if layer == "direct_unsigned" or directness in ("binding", "direct"):
                binding_sources.add(source_name)
        if len(signed) != 1:
            if len(signed) > 1:
                summary["sign_conflicts"] += 1
            continue
        relation = next(iter(signed))
        signed_rows = signed[relation]
        signed_sources = {row[0] for row in signed_rows}
        signed_layers = {row[2] for row in signed_rows}
        has_direct_signed = any(
            row[2] == "direct_signed" and row[3] == "direct" for row in signed_rows
        )
        has_perturbation = "perturbation_signed" in signed_layers
        has_orthology = "orthology_transferred" in signed_layers
        has_putative_direct = any(
            row[2] == "direct_signed" and row[3] == "putative_direct" for row in signed_rows
        )
        if has_direct_signed:
            support_class = "direct_signed"
            confidence = max(0.65, max(row[1] for row in signed_rows))
            evidence_tier = "supported"
            probability = min(0.97, max(0.72, confidence))
        elif has_perturbation and binding_sources and (species, relation) in calibrated_classes:
            support_class = "binding_plus_perturbation"
            confidence = min(0.88, 0.60 + 0.05 * min(len(binding_sources), 3)
                             + 0.04 * min(len(signed_sources), 3))
            evidence_tier = "supported"
            probability = min(0.92, confidence)
        elif has_perturbation and binding_sources:
            support_class = "binding_plus_uncalibrated_perturbation"
            confidence = max(0.48, min(0.64, max(row[1] for row in signed_rows)))
            evidence_tier = "exploratory"
            probability = min(0.64, max(0.35, confidence))
        elif has_putative_direct:
            support_class = "putative_direct_signed"
            confidence = max(0.40, min(0.60, max(row[1] for row in signed_rows)))
            evidence_tier = "exploratory"
            probability = min(0.62, max(0.35, confidence))
        elif has_perturbation:
            support_class = "perturbation_only"
            confidence = max(0.45, min(0.60, max(row[1] for row in signed_rows)))
            evidence_tier = "exploratory"
            probability = min(0.60, max(0.35, confidence))
        elif has_orthology:
            support_class = "conserved_orthology"
            confidence = max(0.40, min(0.58, max(row[1] for row in signed_rows)))
            evidence_tier = "exploratory"
            probability = min(0.58, max(0.30, confidence))
        else:
            summary["insufficient_support"] += 1
            continue
        old = existing.get((source_id, target_id))
        if old and old[0] in ("activation", "repression"):
            status = "corroborated" if old[0] == relation else "conflict"
        elif old:
            # Completing the sign of an observed unsigned binding pair changes the
            # signed graph, so it remains an explicit opt-in candidate.
            status = "candidate"
        else:
            status = "candidate"
        sources = sorted(signed_sources | binding_sources)
        candidate_metadata = {
            "signed_sources": sorted(signed_sources),
            "binding_sources": sorted(binding_sources),
            "calibration_gate_pass": (species, relation) in calibrated_classes,
        }
        if (species, source_id, target_id) in consensus:
            candidate_metadata["perturbation_consensus"] = consensus[
                (species, source_id, target_id)
            ]
        output.append((species, source_id, target_id, relation, confidence, support_class,
                       json.dumps(sources), json.dumps(sorted(layers)), status,
                       evidence_tier, probability,
                       json.dumps(candidate_metadata, sort_keys=True)))
        summary[status] += 1
        summary[support_class] += 1
    conn.executemany("INSERT INTO regulatory_edge_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", output)
    conn.commit()
    summary["stored"] = len(output)
    return dict(summary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        result = build(conn)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
