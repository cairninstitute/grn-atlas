#!/usr/bin/env python3
"""Create conservative signed-edge transfers across strict one-to-one orthologs."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from external_evidence import begin_import, finish_import, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
SOURCE = "Conserved signed orthology"
VERSION = "v1"


def build(conn: sqlite3.Connection) -> dict:
    species = {row[0]: row[1] for row in conn.execute("SELECT id,species FROM genes")}
    is_tf = {row[0]: bool(row[1]) for row in conn.execute("SELECT id,is_tf FROM genes")}
    maps: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    target_species_by_gene: dict[str, set[str]] = defaultdict(set)
    for a, b, species_a, species_b, rel_type in conn.execute(
        "SELECT gene_a,gene_b,species_a,species_b,rel_type FROM orthologs WHERE rel_type IN ('1:1','one2one')"
    ):
        maps[(a, species_b)].append((b, species_a))
        maps[(b, species_a)].append((a, species_b))
        target_species_by_gene[a].add(species_b)
        target_species_by_gene[b].add(species_a)

    support: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    confidence: dict[tuple[str, str, str, str], float] = {}
    for source, target, sign, edge_conf in conn.execute(
        "SELECT source_id,target_id,sign,confidence FROM interactions "
        "WHERE sign IN ('activation','repression') AND sign_evidence IN ('measured','perturbation')"
    ):
        donor_species = species.get(source)
        if not donor_species:
            continue
        for target_species in target_species_by_gene.get(source, set()):
            source_maps = maps.get((source, target_species), [])
            target_maps = maps.get((target, target_species), [])
            if len(source_maps) != 1 or len(target_maps) != 1:
                continue
            projected_source = source_maps[0][0]
            projected_target = target_maps[0][0]
            if projected_source == projected_target or not is_tf.get(projected_source):
                continue
            key = (target_species, projected_source, projected_target, sign)
            support[key].add(donor_species)
            confidence[key] = max(confidence.get(key, 0.0), min(0.58, float(edge_conf) * 0.62))

    cis_pairs = set()
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cis_support_edges'").fetchone():
        cis_pairs = {(row[0], row[1]) for row in conn.execute(
            "SELECT source_id,target_id FROM cis_support_edges WHERE score>=0.5"
        )}
    rows = []
    for (target_species, source, target, sign), donors in sorted(support.items()):
        # One donor is accepted only with independent target-species cis support.
        if len(donors) < 2 and (source, target) not in cis_pairs:
            continue
        rows.append({
            "species": target_species,
            "source_id": source,
            "target_id": target,
            "relation_type": sign,
            "evidence_layer": "orthology_transferred",
            "directness": "conserved",
            "record_key": f"{target_species}|{source}|{target}|{sign}",
            "confidence": confidence[(target_species, source, target, sign)],
            "metadata": {"donor_species": sorted(donors), "cis_supported": (source, target) in cis_pairs},
        })
    run_id = begin_import(conn, SOURCE, VERSION, "local://orthologs+signed-interactions", None)
    stored = replace_source_evidence(conn, SOURCE, VERSION, run_id, rows)
    accepted_keys = {
        (row["species"], row["source_id"], row["target_id"], row["relation_type"])
        for row in rows
    }
    result = {
        "stored": stored,
        "multi_species": sum(len(support[key]) >= 2 for key in accepted_keys),
        "cis_rescued": sum(len(support[key]) == 1 for key in accepted_keys),
    }
    finish_import(conn, run_id, result)
    return result


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
