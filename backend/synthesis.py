"""Atlas-grounded evidence synthesis for GRN Atlas workflows."""

from __future__ import annotations

import json
from typing import Any

import briefing
import evidence
import packet
import provenance


def _conn(db_or_conn):
    return db_or_conn.conn if hasattr(db_or_conn, "conn") else db_or_conn


def _source_keys_for_candidate(candidate: dict[str, Any], citation_bundle: dict[str, Any]) -> list[str]:
    names = set(candidate.get("evidence_summary", {}).get("sources", []))
    support_counts = candidate.get("evidence_summary", {}).get("support_counts", {})
    out = []
    for src in citation_bundle.get("sources", []):
        key = src.get("key")
        name = src.get("name", "")
        if key == "jaspar2024" and support_counts.get("motif_supported", 0) > 0:
            out.append(key)
        elif key == "gwascatalog" and support_counts.get("trait_supported", 0) > 0:
            out.append(key)
        elif key == "plantreactome" and support_counts.get("pathway_supported", 0) > 0:
            out.append(key)
        elif key == "plaza" and support_counts.get("orthology_projected", 0) > 0:
            out.append(key)
        elif any(src_name in name for src_name in names):
            out.append(key)
    return sorted(dict.fromkeys(out))


def _pmids_for_gene(conn, gene_id: str) -> list[str]:
    seen: list[str] = []
    for row in conn.execute(
        "SELECT pmids FROM interactions WHERE source_id = ? OR target_id = ?",
        (gene_id, gene_id),
    ).fetchall():
        try:
            values = json.loads(row["pmids"] or "[]")
        except Exception:
            values = []
        for pmid in values:
            pmid = str(pmid).strip()
            if pmid and pmid not in seen:
                seen.append(pmid)
    for row in conn.execute(
        "SELECT pubmed_id FROM trait_associations WHERE gene_id = ? AND pubmed_id IS NOT NULL AND pubmed_id != ''",
        (gene_id,),
    ).fetchall():
        pmid = str(row["pubmed_id"]).strip()
        if pmid and pmid not in seen:
            seen.append(pmid)
    return seen


def _support_summary(candidate: dict[str, Any], audit: dict[str, Any]) -> list[str]:
    counts = audit.get("evidence_summary", {}).get("support_counts", {})
    out = [
        f"{candidate.get('symbol') or candidate.get('gene_id')} has {candidate.get('confidence', {}).get('label', 'unknown')} atlas support.",
    ]
    if counts.get("curated", 0) > 0:
        out.append(f"curated regulatory evidence is present ({counts['curated']} record(s))")
    if counts.get("motif_supported", 0) > 0:
        out.append(f"motif support is present ({counts['motif_supported']} hit(s))")
    if counts.get("pathway_supported", 0) > 0:
        out.append(f"pathway context is present ({counts['pathway_supported']} annotation(s))")
    if counts.get("trait_supported", 0) > 0:
        out.append(f"trait context is present ({counts['trait_supported']} association(s))")
    if counts.get("orthology_projected", 0) > 0:
        out.append(f"orthology/projected support is present ({counts['orthology_projected']} signal(s))")
    if counts.get("inferred_expression", 0) > 0:
        out.append(f"inferred expression support is present ({counts['inferred_expression']} edge(s))")
    return out


def _weakness_summary(candidate: dict[str, Any], audit: dict[str, Any]) -> list[str]:
    counts = audit.get("evidence_summary", {}).get("support_counts", {})
    gaps = candidate.get("coverage_gaps", []) or audit.get("coverage_gaps", [])
    out = []
    if counts.get("curated", 0) == 0:
        out.append("no curated regulatory evidence is present for this candidate in the loaded atlas")
    if counts.get("motif_supported", 0) == 0:
        out.append("no motif corroboration is currently loaded for this candidate")
    if counts.get("pathway_supported", 0) == 0 and counts.get("trait_supported", 0) == 0:
        out.append("functional context is thin because pathway and trait layers are absent or sparse")
    if counts.get("orthology_projected", 0) > 0 and counts.get("curated", 0) == 0:
        out.append("support is dominated by projected orthology rather than same-species direct evidence")
    if counts.get("inferred_expression", 0) > 0 and counts.get("curated", 0) == 0:
        out.append("support is dominated by inferred expression edges rather than direct curated interactions")
    for gap in gaps[:3]:
        out.append(gap.get("detail", "coverage gap present"))
    if not out:
        out.append("no explicit contradictory evidence is stored; the main remaining risk is incomplete layer coverage")
    return out


def _reporting_caveats(candidate: dict[str, Any], pmids: list[str]) -> list[str]:
    caveats = [
        "This synthesis is atlas-grounded and does not retrieve external literature beyond PMIDs already stored in the database.",
        "The atlas does not encode explicit negative or contradictory wet-lab results; weak evidence should not be overread as refutation.",
    ]
    for gap in candidate.get("coverage_gaps", [])[:2]:
        caveats.append(gap.get("detail", "coverage gap present"))
    if not pmids:
        caveats.append("No PubMed IDs were attached to the current candidate evidence in the loaded atlas.")
    return caveats


def _candidate_narrative(candidate: dict[str, Any], audit: dict[str, Any], pmids: list[str]) -> str:
    symbol = candidate.get("symbol") or candidate.get("gene_id")
    confidence = candidate.get("confidence", {}).get("label", "unknown")
    counts = audit.get("evidence_summary", {}).get("support_counts", {})
    strengths = []
    if counts.get("curated", 0) > 0:
        strengths.append("curated regulation")
    if counts.get("motif_supported", 0) > 0:
        strengths.append("motif support")
    if counts.get("pathway_supported", 0) > 0:
        strengths.append("pathway context")
    if counts.get("trait_supported", 0) > 0:
        strengths.append("trait context")
    strengths_text = ", ".join(strengths) if strengths else "limited direct support"
    pmid_text = f" PubMed support: {', '.join(pmids[:5])}." if pmids else ""
    return (
        f"{symbol} is currently summarized as {confidence} confidence based on {strengths_text}. "
        f"The current atlas view should be treated as a support synthesis, not a full literature review."
        f"{pmid_text}"
    )


def build_evidence_synthesis(db, gene_ids: list[str], intent: str = "experiment",
                             species: str | None = None, max_candidates: int = 3,
                             max_experiments: int = 3) -> dict[str, Any]:
    conn = _conn(db)
    brief = briefing.build_research_brief(
        db,
        gene_ids,
        intent=intent,
        species=species,
        max_candidates=max_candidates,
        max_experiments=max_experiments,
    )
    packet_data = packet.build_study_packet(
        db,
        gene_ids,
        intent=intent,
        species=species,
        max_candidates=max_candidates,
        max_experiments=max_experiments,
    )
    candidates = brief.get("candidate_brief", [])[:max_candidates]
    synthesized = []
    for candidate in candidates:
        audit = evidence.summarize_gene_evidence(db, candidate["gene_id"])
        pmids = _pmids_for_gene(conn, candidate["gene_id"])
        synthesized.append({
            "gene_id": candidate.get("gene_id"),
            "symbol": candidate.get("symbol"),
            "species": candidate.get("species"),
            "confidence": audit.get("confidence"),
            "support_summary": _support_summary(candidate, audit),
            "contradictory_or_weak_evidence": _weakness_summary(candidate, audit),
            "atlas_pmids": pmids,
            "source_keys": _source_keys_for_candidate(candidate, packet_data.get("citation_bundle", {})),
            "source_names": audit.get("evidence_summary", {}).get("sources", []),
            "narrative": _candidate_narrative(candidate, audit, pmids),
            "reporting_caveats": _reporting_caveats(candidate, pmids),
        })

    lead = synthesized[0] if synthesized else None
    freshness = provenance.freshness()
    overall_caveats = [
        "Only atlas-loaded evidence layers are summarized here.",
        "Use the cited atlas sources and stored PMIDs as starting points for downstream manuscript or slide preparation.",
    ]
    overall_caveats.extend((lead or {}).get("reporting_caveats", [])[:2])

    return {
        "title": f"Evidence synthesis for {intent} follow-up",
        "intent": intent,
        "species": species,
        "brief": brief,
        "lead_candidate": lead,
        "candidate_syntheses": synthesized,
        "citation_bundle": packet_data.get("citation_bundle", {}),
        "provenance_freshness": {
            "checked": freshness.get("checked"),
            "stale_sources": freshness.get("stale", []),
        },
        "overall_support_summary": [
            f"{len(synthesized)} candidate synthesis block(s) were generated.",
            f"Lead candidate is {(lead or {}).get('symbol') or (lead or {}).get('gene_id')}." if lead else "No lead candidate identified.",
            f"{len(packet_data.get('citation_bundle', {}).get('source_keys', []))} citation source(s) were selected.",
        ],
        "overall_caveats": overall_caveats,
        "summary": [
            "This output is designed for paper-style or collaborator-facing evidence summaries.",
            "It reports atlas-backed support, weak/indirect evidence, stored PMIDs, and citation context.",
            "It does not claim to replace external literature review.",
        ],
    }
