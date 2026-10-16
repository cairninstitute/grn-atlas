#!/usr/bin/env python3
"""Build auditable cross-species signed-edge transfer candidates."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from external_evidence import begin_import, ensure_schema, finish_import, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
SOURCE = "Conserved signed orthology"
VERSION = "v2"
SIGNED = {"activation", "repression"}


def _json_list(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _ensure_transfer_schema(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)
    conn.executescript("""
        DROP TABLE IF EXISTS orthology_transfer_mappings;
        CREATE TABLE orthology_transfer_mappings (
            source_gene TEXT NOT NULL, target_gene TEXT NOT NULL,
            source_species TEXT NOT NULL, target_species TEXT NOT NULL,
            mapping_class TEXT NOT NULL, score REAL NOT NULL,
            status TEXT NOT NULL, reason TEXT NOT NULL,
            PRIMARY KEY(source_gene,target_gene,target_species,mapping_class)
        );
        CREATE INDEX idx_otm_source ON orthology_transfer_mappings(source_gene,target_species,status);
        DROP TABLE IF EXISTS orthology_transfer_candidates;
        CREATE TABLE orthology_transfer_candidates (
            species TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL, mapping_class TEXT NOT NULL,
            mapping_score REAL NOT NULL, donor_species TEXT NOT NULL,
            donor_edges TEXT NOT NULL, donor_sources TEXT NOT NULL, donor_pmids TEXT NOT NULL,
            donor_species_count INTEGER NOT NULL, independent_donor_count INTEGER NOT NULL,
            recipient_binding_sources TEXT NOT NULL, recipient_cis_support INTEGER NOT NULL,
            source_independent INTEGER NOT NULL, edge_score REAL NOT NULL, sign_score REAL NOT NULL,
            status TEXT NOT NULL, conflict_reason TEXT, metadata TEXT NOT NULL,
            PRIMARY KEY(species,source_id,target_id,relation_type)
        );
        CREATE INDEX idx_otc_species_status
            ON orthology_transfer_candidates(species,status,mapping_class,relation_type);
    """)


def _normalize_mappings(conn: sqlite3.Connection) -> dict[tuple[str, str], list[dict]]:
    raw = conn.execute(
        "SELECT gene_a,gene_b,species_a,species_b,COALESCE(rel_type,''),COALESCE(score,0.5) "
        "FROM orthologs"
    ).fetchall()
    synteny_degree: dict[tuple[str, str], set[str]] = defaultdict(set)
    for a, b, species_a, species_b, rel_type, _ in raw:
        if rel_type == "synteny":
            synteny_degree[(a, species_b)].add(b)
            synteny_degree[(b, species_a)].add(a)

    rows = []
    accepted: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for a, b, species_a, species_b, rel_type, score in raw:
        if rel_type in {"1:1", "one2one"}:
            mapping_class, status, reason = "explicit_one_to_one", "accepted", "explicit_one_to_one"
        elif rel_type == "synteny":
            reciprocal_unique = (
                len(synteny_degree[(a, species_b)]) == 1
                and len(synteny_degree[(b, species_a)]) == 1
            )
            mapping_class = "reciprocal_unique_synteny"
            status = "accepted" if reciprocal_unique else "excluded"
            reason = "reciprocal_unique" if reciprocal_unique else "ambiguous_synteny"
        else:
            mapping_class, status, reason = "ambiguous_family", "excluded", rel_type or "unknown"
        normalized_score = min(1.0, max(0.0, float(score)))
        for source, target, source_species, target_species in (
            (a, b, species_a, species_b), (b, a, species_b, species_a),
        ):
            rows.append((source, target, source_species, target_species, mapping_class,
                         normalized_score, status, reason))
            if status == "accepted":
                accepted[(source, target_species)].append({
                    "target": target, "class": mapping_class, "score": normalized_score,
                })
    conn.executemany("INSERT OR IGNORE INTO orthology_transfer_mappings VALUES (?,?,?,?,?,?,?,?)", rows)
    return accepted


def build(conn: sqlite3.Connection) -> dict:
    _ensure_transfer_schema(conn)
    mappings = _normalize_mappings(conn)
    mapped_species: dict[str, set[str]] = defaultdict(set)
    for source_gene, target_species in mappings:
        mapped_species[source_gene].add(target_species)
    species = dict(conn.execute("SELECT id,species FROM genes"))
    is_tf = {row[0]: bool(row[1]) for row in conn.execute("SELECT id,is_tf FROM genes")}

    recipient_binding: dict[tuple[str, str], set[str]] = defaultdict(set)
    for source, target, source_name in conn.execute(
        "SELECT source_id,target_id,source_name FROM regulatory_evidence "
        "WHERE source_name<>? AND (evidence_layer='direct_unsigned' "
        "OR (evidence_layer='direct_signed' AND directness IN ('direct','binding')))",
        (SOURCE,),
    ):
        recipient_binding[(source, target)].add(source_name)
    cis_pairs = set()
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cis_support_edges'").fetchone():
        cis_pairs = {(row[0], row[1]) for row in conn.execute(
            "SELECT source_id,target_id FROM cis_support_edges WHERE score>=0.5"
        )}

    projections: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for source, target, sign, confidence, source_json, pmid_json, sign_evidence in conn.execute(
        "SELECT source_id,target_id,COALESCE(sign,regulation_type),confidence,sources,pmids,sign_evidence "
        "FROM interactions WHERE COALESCE(sign,regulation_type) IN ('activation','repression') "
        "AND sign_evidence IN ('measured','perturbation')"
    ):
        measured_sources = [
            item for item in _json_list(source_json)
            if not item.startswith("Inferred:") and item != SOURCE
        ]
        if not measured_sources:
            continue
        donor_species = species.get(source)
        if not donor_species:
            continue
        for recipient_species in mapped_species.get(source, set()):
            source_maps = mappings.get((source, recipient_species), [])
            target_maps = mappings.get((target, recipient_species), [])
            if len(source_maps) != 1 or len(target_maps) != 1:
                continue
            projected_source = source_maps[0]["target"]
            projected_target = target_maps[0]["target"]
            if projected_source == projected_target or not is_tf.get(projected_source):
                continue
            mapping_class = (
                "explicit_one_to_one" if source_maps[0]["class"] == target_maps[0]["class"] == "explicit_one_to_one"
                else "reciprocal_unique_synteny"
            )
            projections[(recipient_species, projected_source, projected_target, sign)].append({
                "donor_species": donor_species, "source_id": source, "target_id": target,
                "confidence": float(confidence), "sources": measured_sources,
                "pmids": _json_list(pmid_json), "sign_evidence": sign_evidence,
                "mapping_class": mapping_class,
                "mapping_score": min(source_maps[0]["score"], target_maps[0]["score"]),
            })

    projected_pairs = {(key[1], key[2]) for key in projections}
    expression_context: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='edge_tissue_weights'"
    ).fetchone():
        for source, target, tissue, weight in conn.execute(
            "SELECT source_id,target_id,tissue,coexpression FROM edge_tissue_weights"
        ):
            if (source, target) in projected_pairs and abs(float(weight)) >= 0.3:
                expression_context[(source, target)].append((tissue, float(weight)))

    pair_signs: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for species_id, source, target, sign in projections:
        pair_signs[(species_id, source, target)].add(sign)

    table_rows = []
    evidence_rows = []
    counts = defaultdict(int)
    for key, donors in sorted(projections.items()):
        recipient_species, source, target, sign = key
        donor_species = sorted({row["donor_species"] for row in donors})
        donor_sources = sorted({item for row in donors for item in row["sources"]})
        donor_pmids = sorted({item for row in donors for item in row["pmids"]})
        independent_donors = {(row["donor_species"], item) for row in donors
                              for item in (row["sources"] or [row["sign_evidence"]])}
        binding_sources = sorted(recipient_binding.get((source, target), set()))
        cis_supported = (source, target) in cis_pairs
        source_independent = not set(donor_sources).intersection(binding_sources)
        mapping_class = (
            "explicit_one_to_one" if all(row["mapping_class"] == "explicit_one_to_one" for row in donors)
            else "reciprocal_unique_synteny"
        )
        mapping_score = max(row["mapping_score"] for row in donors)
        recipient_supported = bool(binding_sources or cis_supported)
        conflict = len(pair_signs[(recipient_species, source, target)]) > 1
        qualified = not conflict and (recipient_supported or len(donor_species) >= 2)
        status = "sign_conflict" if conflict else ("qualified" if qualified else "unvalidated")
        edge_score = min(0.92, 0.38 + 0.16 * (mapping_class == "explicit_one_to_one")
                         + 0.12 * (mapping_class == "reciprocal_unique_synteny")
                         + 0.14 * recipient_supported + 0.06 * min(len(donor_species), 2)
                         + 0.04 * source_independent)
        sign_score = min(0.90, 0.42 + 0.12 * max(row["confidence"] for row in donors)
                         + 0.10 * min(len(donor_species), 2) + 0.08 * recipient_supported)
        metadata = {
            "mapping_class": mapping_class, "mapping_score": mapping_score,
            "recipient_binding_sources": binding_sources, "recipient_cis_support": cis_supported,
            "source_independent": source_independent, "donor_species": donor_species,
            "donor_sources": donor_sources, "edge_score": round(edge_score, 6),
            "sign_score": round(sign_score, 6), "score_semantics": "uncalibrated_rank",
            "transfer_status": status,
            "recipient_expression_context": [
                {"tissue": tissue, "coexpression": round(weight, 6)}
                for tissue, weight in sorted(
                    expression_context.get((source, target), []),
                    key=lambda item: (-abs(item[1]), item[0]),
                )[:5]
            ],
        }
        donor_edges = [{k: row[k] for k in ("donor_species", "source_id", "target_id", "confidence",
                                             "sources", "pmids", "sign_evidence")} for row in donors]
        table_rows.append((recipient_species, source, target, sign, mapping_class, mapping_score,
                           json.dumps(donor_species), json.dumps(donor_edges, sort_keys=True),
                           json.dumps(donor_sources), json.dumps(donor_pmids), len(donor_species),
                           len(independent_donors), json.dumps(binding_sources), int(cis_supported),
                           int(source_independent), edge_score, sign_score, status,
                           "donor_sign_disagreement" if conflict else None,
                           json.dumps(metadata, sort_keys=True)))
        counts[status] += 1
        counts[f"recipient:{recipient_species}"] += 1
        if not conflict:
            evidence_rows.append({
                "species": recipient_species, "source_id": source, "target_id": target,
                "relation_type": sign, "evidence_layer": "orthology_transferred",
                "directness": "conserved" if qualified else "conserved_unvalidated",
                "record_key": f"{recipient_species}|{source}|{target}|{sign}",
                "confidence": min(edge_score, sign_score, 0.58 if qualified else 0.52),
                "pmids": donor_pmids,
                "metadata": metadata,
            })
    conn.executemany("INSERT INTO orthology_transfer_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", table_rows)
    run_id = begin_import(conn, SOURCE, VERSION, "local://orthologs+signed-interactions", None)
    stored = replace_source_evidence(conn, SOURCE, VERSION, run_id, evidence_rows)
    counts.update({"projected": len(table_rows), "stored": stored,
                   "normalized_mappings": conn.execute(
                       "SELECT COUNT(*) FROM orthology_transfer_mappings WHERE status='accepted'"
                   ).fetchone()[0]})
    finish_import(conn, run_id, dict(counts))
    return dict(counts)


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
