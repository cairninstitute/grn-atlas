"""Shareable study packet assembly for GRN Atlas workflows."""

from __future__ import annotations

from typing import Any

import briefing
import provenance
import validation


SOURCE_KEY_BY_NAME = {
    "TRRUST": "trrust2",
    "PlantRegMap": "plantregmap",
    "JASPAR2024": "jaspar2024",
    "GWAS Catalog": "gwascatalog",
    "PlantReactome": "plantreactome",
    "Reactome": "plantreactome",
    "WikiPathways": "mygene",
    "Inferred:Arabidopsis": "plaza",
    "Inferred:Expression": "mygene",
}


def _citation_bundle(brief: dict[str, Any], intent: str) -> dict[str, Any]:
    selected = set()
    for candidate in brief.get("candidate_brief", []):
        sources = candidate.get("evidence_summary", {}).get("sources", [])
        for src in sources:
            key = SOURCE_KEY_BY_NAME.get(src)
            if key:
                selected.add(key)
        counts = candidate.get("evidence_summary", {}).get("support_counts", {})
        if counts.get("motif_supported", 0) > 0:
            selected.add("jaspar2024")
        if counts.get("trait_supported", 0) > 0:
            selected.add("gwascatalog")
        if counts.get("pathway_supported", 0) > 0:
            selected.add("plantreactome")
        if counts.get("orthology_projected", 0) > 0:
            selected.add("plaza")
    if intent in ("experiment", "network", "rnai"):
        selected.update({"oma", "mygene"})

    chosen = [src for src in provenance.SOURCES if src["key"] in selected]
    bib = provenance.bibtex()
    excerpts = []
    for src in chosen:
        marker = f"@article{{{src['key']},"
        start = bib.find(marker)
        if start >= 0:
            end = bib.find("\n\n@", start + 1)
            excerpts.append(bib[start:] if end == -1 else bib[start:end])
    return {
        "source_keys": [src["key"] for src in chosen],
        "sources": chosen,
        "bibtex_excerpt": "\n\n".join(excerpts) + ("\n" if excerpts else ""),
    }


def _hints_for_collaborator(brief: dict[str, Any], validation_plan: dict[str, Any]) -> list[str]:
    hints = []
    candidate_brief = brief.get("candidate_brief") or []
    lead = candidate_brief[0] if candidate_brief else {}
    if lead:
        hints.append(
            f"Start with {lead.get('symbol') or lead.get('gene_id')} because it is the lead candidate in the current brief."
        )
    ready_tracks = [t for t in validation_plan.get("validation_tracks", []) if t.get("ready_to_run")]
    if ready_tracks:
        hints.append(f"{len(ready_tracks)} validation track(s) are ready to run without new blockers.")
    else:
        hints.append("No validation track is fully ready to run; review blockers first.")
    if brief.get("risk_flags"):
        hints.append("Review risk flags before handing this packet to a collaborator or starting wet-lab work.")
    return hints


def _harness_metadata(brief: dict[str, Any], validation_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "lead_candidate": (brief.get("candidate_brief") or [{}])[0].get("gene_id") if brief.get("candidate_brief") else None,
        "workflow_steps": len(brief.get("workflow_plan", [])),
        "validation_tracks": len(validation_plan.get("validation_tracks", [])),
        "risk_flags": len(validation_plan.get("risk_flags", [])),
    }


def build_study_packet(db, gene_ids: list[str], intent: str = "experiment",
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
    vplan = validation.build_validation_plan(
        db,
        gene_ids,
        intent=intent,
        species=species,
        max_candidates=max_candidates,
        max_experiments=max_experiments,
    )
    citation_bundle = _citation_bundle(brief, intent)
    freshness = provenance.freshness()

    handoff = {
        "audience": "collaborator",
        "summary": brief.get("executive_summary", []),
        "execution_hints": _hints_for_collaborator(brief, vplan),
        "handoff_checklist": [
            "confirm the lead candidate still matches the biological question",
            "review blockers and decision gates before starting validation work",
            "use the cited data sources when reporting or sharing derived conclusions",
        ],
    }

    return {
        "title": f"Study packet for {intent} follow-up",
        "intent": intent,
        "species": species,
        "brief": brief,
        "validation_plan": vplan,
        "handoff": handoff,
        "citation_bundle": citation_bundle,
        "freshness_summary": {
            "checked": freshness.get("checked"),
            "stale_sources": freshness.get("stale", []),
        },
        "packet_metadata": _harness_metadata(brief, vplan),
    }
