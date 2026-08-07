"""High-level research brief generation for GRN Atlas workflows."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import context
import evidence
import planning


def _workflow_steps(intent: str, top_candidates: list[dict[str, Any]], plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    steps = []
    candidate_ids = [c["gene_id"] for c in top_candidates[:3]]
    if candidate_ids:
        steps.append({
            "step": 1,
            "action": "audit_support",
            "title": "Audit evidence for the lead candidates",
            "skills": ["grn-evidence-audit"],
            "genes": candidate_ids,
            "reason": "confirm which candidates are backed by curated, motif, expression, pathway, or trait evidence before committing effort",
        })
    if top_candidates:
        species = top_candidates[0].get("species")
        steps.append({
            "step": 2,
            "action": "check_species_readiness",
            "title": "Confirm species-layer readiness for the intended analysis",
            "skills": ["grn-coverage-report"],
            "species": species,
            "reason": "ensure the required layers are present and note any missing optional evidence that may narrow interpretation",
        })
    if plans:
        best = plans[0].get("recommended_experiments", [])
        if best:
            lead = best[0]
            steps.append({
                "step": 3,
                "action": "run_lead_followup",
                "title": f"Run the lead follow-up: {lead['experiment']}",
                "skills": lead.get("recommended_skills", []),
                "reason": lead.get("rationale"),
            })
    if intent == "rnai":
        steps.append({
            "step": len(steps) + 1,
            "action": "validate_rnai_design",
            "title": "Validate RNAi specificity and predicted downstream response",
            "skills": ["grn-dsrna", "grn-perturbation", "grn-evidence-audit"],
            "reason": "RNAi plans should check off-target burden and whether predicted knockdown effects match the biological goal",
        })
    elif intent in ("network", "experiment"):
        steps.append({
            "step": len(steps) + 1,
            "action": "cross_validate_network_hypothesis",
            "title": "Cross-validate the network hypothesis with orthogonal layers",
            "skills": ["grn-network", "grn-perturbation", "grn-motif", "grn-conservation"],
            "reason": "network conclusions are stronger when supported by perturbation, binding, or conservation context",
        })
    return steps


def _risk_flags(top_candidates: list[dict[str, Any]], species_reports: list[dict[str, Any]], plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags = []
    for report in species_reports:
        for gap in report.get("coverage_gaps", []):
            if gap.get("importance") == "required":
                flags.append({
                    "type": "coverage_gap",
                    "scope": report.get("species"),
                    "detail": gap.get("detail"),
                })
    for candidate in top_candidates:
        if candidate.get("confidence", {}).get("label") in ("low", "unsupported"):
            flags.append({
                "type": "weak_support",
                "scope": candidate.get("gene_id"),
                "detail": f"{candidate.get('gene_id')} has {candidate.get('confidence', {}).get('label')} support.",
            })
    for plan in plans:
        if plan.get("coverage_gaps"):
            flags.append({
                "type": "narrow_followup",
                "scope": plan.get("gene_id"),
                "detail": f"{plan.get('gene_id')} follow-up is constrained by {len(plan['coverage_gaps'])} coverage gap(s).",
            })
    return flags


def _species_reports(db, top_candidates: list[dict[str, Any]], intent: str) -> list[dict[str, Any]]:
    by_species = {}
    for candidate in top_candidates:
        species = candidate.get("species")
        if species and species not in by_species:
            by_species[species] = context.build_readiness_report(db, species, intent)
    return list(by_species.values())


def _executive_summary(brief_title: str, top_candidates: list[dict[str, Any]], plans: list[dict[str, Any]], risk_flags: list[dict[str, Any]]) -> list[str]:
    summary = [brief_title]
    if top_candidates:
        lead = top_candidates[0]
        summary.append(
            f"Lead candidate is {lead.get('symbol') or lead.get('gene_id')} ({lead.get('species')}) with priority score {lead.get('priority_score')} and {lead.get('confidence', {}).get('label')} support."
        )
    if plans and plans[0].get("recommended_experiments"):
        lead_exp = plans[0]["recommended_experiments"][0]
        summary.append(f"Top recommended next step is {lead_exp['experiment']} because {lead_exp['rationale']}")
    if risk_flags:
        summary.append(f"There are {len(risk_flags)} explicit risk flag(s) to review before acting on the brief.")
    return summary


def build_research_brief(db, gene_ids: list[str], intent: str = "experiment",
                         species: str | None = None, max_candidates: int = 5,
                         max_experiments: int = 3) -> dict[str, Any]:
    triage = planning.triage_candidates(db, gene_ids, intent=intent, species=species, top_n=max_candidates)
    top_candidates = triage.get("ranked_candidates", [])[:max_candidates]
    prioritization = planning.prioritize_experiments(
        db, [c["gene_id"] for c in top_candidates], intent=intent, species=species,
        max_recommendations=max_experiments,
    )
    plans = prioritization.get("plans", [])
    species_reports = _species_reports(db, top_candidates, intent)
    risks = _risk_flags(top_candidates, species_reports, plans)
    brief_title = f"Research brief for {intent} follow-up"
    workflows = _workflow_steps(intent, top_candidates, plans)
    evidence_snapshots = []
    for candidate in top_candidates[:3]:
        audit = evidence.summarize_gene_evidence(db, candidate["gene_id"])
        evidence_snapshots.append({
            "gene_id": candidate["gene_id"],
            "symbol": candidate.get("symbol"),
            "confidence": audit.get("confidence"),
            "support_counts": audit.get("evidence_summary", {}).get("support_counts", {}),
        })

    by_species = defaultdict(list)
    for candidate in top_candidates:
        by_species[candidate.get("species")].append(candidate["gene_id"])

    return {
        "title": brief_title,
        "intent": intent,
        "species": species,
        "input_gene_count": len(gene_ids),
        "candidate_brief": top_candidates,
        "experiment_brief": plans,
        "species_readiness": species_reports,
        "evidence_snapshots": evidence_snapshots,
        "workflow_plan": workflows,
        "risk_flags": risks,
        "excluded_genes": triage.get("excluded_genes", []),
        "grouping": [{"species": sp, "gene_ids": ids} for sp, ids in by_species.items() if sp],
        "executive_summary": _executive_summary(brief_title, top_candidates, plans, risks),
    }
