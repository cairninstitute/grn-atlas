"""Confidence-boundary analysis for GRN Atlas workflows."""

from __future__ import annotations

from typing import Any

import briefing
import context
import evidence


def _supported_claims(audit: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    claims = []
    counts = audit.get("evidence_summary", {}).get("support_counts", {})
    gene = audit.get("summary", {}).get("gene", {}) or {}
    if counts.get("curated", 0) > 0:
        claims.append(f"{gene.get('symbol') or gene.get('id')} has direct curated regulatory support in the atlas.")
    if counts.get("coexpression_supported", 0) > 0:
        claims.append(f"{gene.get('symbol') or gene.get('id')} has expression/coexpression context in this species.")
    if counts.get("motif_supported", 0) > 0:
        claims.append(f"{gene.get('symbol') or gene.get('id')} has motif-related support in loaded binding layers.")
    if counts.get("trait_supported", 0) > 0:
        claims.append(f"{gene.get('symbol') or gene.get('id')} has trait-associated evidence in the atlas.")
    if readiness.get("readiness_score", 0.0) >= 0.8:
        claims.append(f"{gene.get('species')} has the core layers needed for {readiness.get('intent')} analysis.")
    return claims


def _unsupported_claims(audit: dict[str, Any], readiness: dict[str, Any], intent: str) -> list[str]:
    claims = []
    gene = audit.get("summary", {}).get("gene", {}) or {}
    counts = audit.get("evidence_summary", {}).get("support_counts", {})
    layers = readiness.get("available_layers", {})
    if layers.get("binding_sites", 0) <= 0:
        claims.append(f"cannot claim direct promoter binding for {gene.get('symbol') or gene.get('id')} because binding-site data are not loaded")
    if layers.get("expression_samples", 0) <= 0:
        claims.append(f"cannot claim tissue- or condition-specific expression behavior for {gene.get('symbol') or gene.get('id')} from this atlas state")
    if intent == "rnai" and layers.get("expression_samples", 0) <= 0:
        claims.append(f"cannot support RNAi-specific prioritization without expression-backed transcript context for {gene.get('species')}")
    if counts.get("curated", 0) <= 0 and counts.get("orthology_projected", 0) > 0:
        claims.append(f"cannot treat {gene.get('symbol') or gene.get('id')} as directly validated; support is projected rather than curated")
    if audit.get("confidence", {}).get("label") in ("low", "unsupported"):
        claims.append(f"cannot make a strong prioritization claim for {gene.get('symbol') or gene.get('id')} from current evidence alone")
    return claims


def _ambiguity_sources(audit: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    out = []
    counts = audit.get("evidence_summary", {}).get("support_counts", {})
    if sum(1 for v in counts.values() if v > 0) <= 1:
        out.append("support comes from only one evidence class")
    if readiness.get("coverage_gaps"):
        out.extend(gap.get("detail") for gap in readiness.get("coverage_gaps", [])[:3])
    if audit.get("confidence", {}).get("label") == "moderate":
        out.append("evidence is mixed enough that follow-up conclusions should stay provisional")
    return out


def _safe_interpretations(audit: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    gene = audit.get("summary", {}).get("gene", {}) or {}
    conf = audit.get("confidence", {}).get("label")
    statements = [
        f"it is reasonable to treat {gene.get('symbol') or gene.get('id')} as a candidate for further review, not as a settled mechanism",
    ]
    if conf in ("high", "moderate"):
        statements.append("network-oriented follow-up is defensible if conclusions stay tied to the loaded evidence layers")
    if readiness.get("coverage_gaps"):
        statements.append("interpret negative or missing support as an atlas coverage limit unless orthogonal evidence also disagrees")
    return statements


def _data_needed(audit: dict[str, Any], readiness: dict[str, Any], intent: str) -> list[str]:
    needed = []
    layers = readiness.get("available_layers", {})
    species = (audit.get("summary", {}).get("gene", {}) or {}).get("species")
    if layers.get("binding_sites", 0) <= 0:
        needed.append(f"binding-site or ChIP-like evidence for {species} to support direct regulatory claims")
    if layers.get("expression_samples", 0) <= 0:
        needed.append(f"expression panel or perturbation-responsive transcript data for {species}")
    if intent == "rnai":
        needed.append("transcript-aware specificity and off-target context before claiming RNAi tractability")
    if audit.get("confidence", {}).get("label") in ("low", "unsupported"):
        needed.append("an orthogonal evidence layer such as curated interactions, motif support, or phenotype linkage")
    return needed


def confidence_boundary(db, gene_ids: list[str], intent: str = "experiment",
                        species: str | None = None, max_candidates: int = 3,
                        max_experiments: int = 3) -> dict[str, Any]:
    brief = briefing.build_research_brief(
        db,
        gene_ids,
        intent=intent,
        species=species,
        max_candidates=max_candidates,
        max_experiments=max_experiments,
    )
    candidates = []
    for candidate in brief.get("candidate_brief", [])[:max_candidates]:
        audit = evidence.summarize_gene_evidence(db, candidate["gene_id"])
        readiness = context.build_readiness_report(db, candidate["species"], intent, candidate["gene_id"])
        candidates.append({
            "gene_id": candidate["gene_id"],
            "symbol": candidate.get("symbol"),
            "species": candidate.get("species"),
            "confidence": audit.get("confidence", {}),
            "supported_claims": _supported_claims(audit, readiness),
            "unsupported_claims": _unsupported_claims(audit, readiness, intent),
            "ambiguity_sources": _ambiguity_sources(audit, readiness),
            "safe_interpretations": _safe_interpretations(audit, readiness),
            "data_needed": _data_needed(audit, readiness, intent),
        })
    lead = candidates[0] if candidates else None
    return {
        "title": f"Confidence boundary for {intent} follow-up",
        "intent": intent,
        "species": species,
        "brief": brief,
        "lead_candidate": lead,
        "candidate_boundaries": candidates,
        "summary": [
            f"Lead candidate is {lead.get('symbol') or lead.get('gene_id')}." if lead else "No lead candidate identified.",
            f"{len(candidates)} candidate boundary profile(s) were generated.",
            "Use unsupported claims and missing-data notes to avoid over-interpreting absent evidence.",
        ],
    }
