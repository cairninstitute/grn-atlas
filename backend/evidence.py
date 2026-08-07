"""Shared evidence summarization helpers for GRN Atlas."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


EVIDENCE_CLASSES = (
    "curated",
    "orthology_projected",
    "inferred_expression",
    "motif_supported",
    "coexpression_supported",
    "pathway_supported",
    "trait_supported",
)


def _conn(db_or_conn):
    return db_or_conn.conn if hasattr(db_or_conn, "conn") else db_or_conn


def _gene_row(db_or_conn, gene_id: str):
    conn = _conn(db_or_conn)
    return conn.execute(
        "SELECT id, symbol, name, species, is_tf, gene_type, synonyms, symbol_source "
        "FROM genes WHERE id = ?",
        (gene_id,),
    ).fetchone()


def _parse_sources(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        out = json.loads(raw)
        return out if isinstance(out, list) else [str(out)]
    except Exception:
        return [raw]


def _base_support_counts() -> dict[str, int]:
    return {k: 0 for k in EVIDENCE_CLASSES}


def confidence_from_evidence(summary: dict[str, Any]) -> dict[str, Any]:
    counts = summary.get("evidence_summary", {}).get("support_counts", {})
    curated = counts.get("curated", 0)
    projected = counts.get("orthology_projected", 0)
    inferred = counts.get("inferred_expression", 0)
    motif = counts.get("motif_supported", 0)
    coexpr = counts.get("coexpression_supported", 0)
    support_types = sum(1 for v in counts.values() if v > 0)

    if curated > 0 and (motif > 0 or coexpr > 0 or support_types >= 2):
        label = "high"
        rationale = "curated support with corroborating evidence"
    elif curated > 0 or (projected > 0 and (motif > 0 or coexpr > 0)) or inferred > 0:
        label = "moderate"
        rationale = "some direct or inferred support is available"
    elif support_types > 0:
        label = "low"
        rationale = "only indirect or sparse evidence is available"
    else:
        label = "unsupported"
        rationale = "no supporting evidence was found in the loaded atlas layers"
    return {"label": label, "support_types": support_types, "rationale": rationale}


def summarize_gene_evidence(db_or_conn, gene_id: str) -> dict[str, Any]:
    conn = _conn(db_or_conn)
    gene = _gene_row(conn, gene_id)
    if gene is None:
        return {
            "query": {"scope": "gene", "gene_id": gene_id},
            "summary": {"supported": False},
            "evidence_summary": {"support_counts": _base_support_counts(), "sources": []},
            "supporting_records": [],
            "coverage_gaps": [{"layer": "gene", "status": "missing", "detail": "gene not found"}],
            "notes": [f"Gene {gene_id} was not found in the atlas."],
        }

    support_counts = _base_support_counts()
    sources_seen: set[str] = set()
    supporting_records = []

    interaction_rows = conn.execute(
        "SELECT source_id, target_id, sources, confidence FROM interactions "
        "WHERE source_id = ? OR target_id = ?",
        (gene_id, gene_id),
    ).fetchall()
    for row in interaction_rows:
        srcs = _parse_sources(row["sources"])
        classes = set()
        if any("Inferred:Arabidopsis" in s for s in srcs):
            classes.add("orthology_projected")
        elif any("Inferred" in s for s in srcs):
            classes.add("inferred_expression")
        else:
            classes.add("curated")
        for klass in classes:
            support_counts[klass] += 1
        sources_seen.update(srcs)
        supporting_records.append({
            "kind": "interaction",
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "confidence": row["confidence"],
            "classes": sorted(classes),
            "sources": srcs,
        })

    motif_count = conn.execute(
        "SELECT COUNT(*) FROM motifs WHERE tf_gene_id = ?",
        (gene_id,),
    ).fetchone()[0]
    if motif_count:
        support_counts["motif_supported"] += motif_count
        supporting_records.append({"kind": "motif_tf", "count": motif_count})

    if gene["species"] in ("arabidopsis", "tomato", "petunia"):
        matrix = None
        try:
            import expression
            matrix = expression.get_matrix(gene["species"])
        except Exception:
            matrix = None
        if matrix and matrix.has(gene_id):
            support_counts["coexpression_supported"] += 1
            supporting_records.append({"kind": "expression_profile", "samples": matrix.n})

    pathway_count = conn.execute(
        "SELECT COUNT(*) FROM pathway_annotations WHERE gene_id = ?",
        (gene_id,),
    ).fetchone()[0]
    if pathway_count:
        support_counts["pathway_supported"] += pathway_count
        supporting_records.append({"kind": "pathway_annotations", "count": pathway_count})

    trait_count = conn.execute(
        "SELECT COUNT(*) FROM trait_associations WHERE gene_id = ?",
        (gene_id,),
    ).fetchone()[0]
    if trait_count:
        support_counts["trait_supported"] += trait_count
        supporting_records.append({"kind": "trait_associations", "count": trait_count})

    orth_count = conn.execute(
        "SELECT COUNT(*) FROM orthologs WHERE gene_a = ? OR gene_b = ?",
        (gene_id, gene_id),
    ).fetchone()[0]

    summary = {
        "query": {"scope": "gene", "gene_id": gene_id},
        "summary": {
            "supported": any(v > 0 for v in support_counts.values()),
            "gene": dict(gene),
            "ortholog_count": orth_count,
        },
        "evidence_summary": {
            "support_counts": support_counts,
            "sources": sorted(sources_seen),
        },
        "supporting_records": supporting_records,
        "coverage_gaps": [],
        "notes": [],
    }
    summary["confidence"] = confidence_from_evidence(summary)
    if not summary["summary"]["supported"]:
        summary["notes"].append("The gene exists, but no supporting evidence layers are populated for this query.")
    return summary


def summarize_edge_evidence(db_or_conn, source_id: str, target_id: str) -> dict[str, Any]:
    conn = _conn(db_or_conn)
    source_gene = _gene_row(conn, source_id)
    target_gene = _gene_row(conn, target_id)
    support_counts = _base_support_counts()
    supporting_records = []
    coverage_gaps = []

    if source_gene is None:
        coverage_gaps.append({"layer": "source_gene", "status": "missing", "detail": f"{source_id} not found"})
    if target_gene is None:
        coverage_gaps.append({"layer": "target_gene", "status": "missing", "detail": f"{target_id} not found"})
    if coverage_gaps:
        summary = {
            "query": {"scope": "edge", "source_id": source_id, "target_id": target_id},
            "summary": {"supported": False},
            "evidence_summary": {"support_counts": support_counts, "sources": []},
            "supporting_records": [],
            "coverage_gaps": coverage_gaps,
            "notes": ["At least one gene in the edge query is not present in the atlas."],
        }
        summary["confidence"] = confidence_from_evidence(summary)
        return summary

    row = conn.execute(
        "SELECT regulation_type, confidence, sources, pmids "
        "FROM interactions WHERE source_id = ? AND target_id = ?",
        (source_id, target_id),
    ).fetchone()
    sources_seen: set[str] = set()
    if row:
        srcs = _parse_sources(row["sources"])
        classes = set()
        if any("Inferred:Arabidopsis" in s for s in srcs):
            classes.add("orthology_projected")
        elif any("Inferred" in s for s in srcs):
            classes.add("inferred_expression")
        else:
            classes.add("curated")
        for klass in classes:
            support_counts[klass] += 1
        sources_seen.update(srcs)
        supporting_records.append({
            "kind": "interaction",
            "regulation_type": row["regulation_type"],
            "confidence": row["confidence"],
            "classes": sorted(classes),
            "sources": srcs,
            "pmids": json.loads(row["pmids"] or "[]"),
        })

    inferred_rows = conn.execute(
        "SELECT method, importance FROM inferred_edges WHERE source_id = ? AND target_id = ?",
        (source_id, target_id),
    ).fetchall()
    if inferred_rows:
        support_counts["inferred_expression"] += len(inferred_rows)
        supporting_records.append({
            "kind": "inferred_edges",
            "records": [{"method": r["method"], "importance": r["importance"]} for r in inferred_rows],
        })

    motif_rows = conn.execute(
        "SELECT COUNT(*) FROM motifs m "
        "JOIN motif_hits h ON h.motif_id = m.motif_id "
        "JOIN gene_id_crosswalk x ON x.ext_gene_id = h.ext_gene_id "
        "WHERE m.tf_gene_id = ? AND x.atlas_gene_id = ?",
        (source_id, target_id),
    ).fetchone()[0]
    if motif_rows:
        support_counts["motif_supported"] += motif_rows
        supporting_records.append({"kind": "motif_support", "count": motif_rows})

    orth_rows = conn.execute(
        "SELECT COUNT(*) FROM orthologs "
        "WHERE (gene_a = ? OR gene_b = ?) OR (gene_a = ? OR gene_b = ?)",
        (source_id, source_id, target_id, target_id),
    ).fetchone()[0]
    if orth_rows:
        support_counts["orthology_projected"] += 1
        supporting_records.append({"kind": "ortholog_context", "count": orth_rows})

    if source_gene["species"] == target_gene["species"] and source_gene["species"] in ("arabidopsis", "tomato", "petunia"):
        try:
            import expression
            matrix = expression.get_matrix(source_gene["species"])
        except Exception:
            matrix = None
        if matrix and matrix.has(source_id) and matrix.has(target_id):
            coexpr = matrix.coexpressed(source_id, top=200, min_abs_r=0.5, min_expr=0.0, candidates=[target_id])
            if coexpr:
                support_counts["coexpression_supported"] += 1
                supporting_records.append({"kind": "coexpression", "r": coexpr[0]["r"]})

    target_pathways = conn.execute(
        "SELECT COUNT(*) FROM pathway_annotations WHERE gene_id = ?",
        (target_id,),
    ).fetchone()[0]
    if target_pathways:
        support_counts["pathway_supported"] += 1
    target_traits = conn.execute(
        "SELECT COUNT(*) FROM trait_associations WHERE gene_id = ?",
        (target_id,),
    ).fetchone()[0]
    if target_traits:
        support_counts["trait_supported"] += 1

    summary = {
        "query": {"scope": "edge", "source_id": source_id, "target_id": target_id},
        "summary": {
            "supported": any(v > 0 for v in support_counts.values()),
            "source_gene": dict(source_gene),
            "target_gene": dict(target_gene),
        },
        "evidence_summary": {
            "support_counts": support_counts,
            "sources": sorted(sources_seen),
        },
        "supporting_records": supporting_records,
        "coverage_gaps": coverage_gaps,
        "notes": [],
    }
    summary["confidence"] = confidence_from_evidence(summary)
    if not summary["summary"]["supported"]:
        summary["notes"].append("No direct or indirect support was found for this edge in the loaded atlas layers.")
    return summary
