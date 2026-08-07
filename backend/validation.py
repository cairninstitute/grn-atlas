"""Execution-ready validation plans for GRN Atlas research workflows."""

from __future__ import annotations

from typing import Any

import briefing


def _required_layers(experiment: str) -> list[str]:
    mapping = {
        "network_perturbation": ["network_edges"],
        "expression_context_review": ["expression_samples"],
        "motif_binding_validation": ["binding_sites"],
        "dsrna_design": ["expression_samples"],
        "trait_association_followup": ["trait_associations"],
        "cross_species_conservation_check": ["orthologs"],
    }
    return mapping.get(experiment, [])


def _success_criteria(experiment: str, intent: str) -> list[str]:
    mapping = {
        "network_perturbation": [
            "predicted direction is coherent across the highest-confidence paths",
            "lead edges are not supported only by weak or unsupported evidence",
        ],
        "expression_context_review": [
            "candidate shows usable expression in the relevant samples or tissues",
            "coexpression context is not dominated by unrelated broad housekeeping signal",
        ],
        "motif_binding_validation": [
            "promoter-level binding support is present for the candidate hypothesis",
            "binding support agrees with the claimed TF-target direction",
        ],
        "dsrna_design": [
            "a designable window exists with acceptable off-target burden",
            "predicted knockdown effect aligns with the desired phenotype or pathway outcome",
        ],
        "trait_association_followup": [
            "trait enrichments or direct associations are not driven by a trivial single-record artifact",
            "trait context is relevant to the biological question being asked",
        ],
        "cross_species_conservation_check": [
            "the same regulatory relationship is observed or plausibly transferred across orthologs",
            "species-specific divergence is explicitly recognized if conservation is absent",
        ],
    }
    crit = mapping.get(experiment, ["result is supported by at least one independent evidence layer"])
    if intent == "rnai" and experiment == "dsrna_design":
        crit = crit + ["specificity is high enough to justify wet-lab follow-up"]
    return crit


def _failure_signals(experiment: str) -> list[str]:
    mapping = {
        "network_perturbation": [
            "support depends entirely on projected or low-confidence edges",
            "predicted downstream direction changes collapse when modest confidence filters are applied",
        ],
        "expression_context_review": [
            "candidate is effectively unexpressed in the relevant context",
            "expression support exists only in unrelated tissues or conditions",
        ],
        "motif_binding_validation": [
            "no promoter support is found in the loaded assembly",
            "binding evidence contradicts the proposed regulator-target mapping",
        ],
        "dsrna_design": [
            "no acceptable design window can be found",
            "off-target burden is too high for a credible RNAi experiment",
        ],
        "trait_association_followup": [
            "trait signal is too sparse or biologically disconnected from the study question",
        ],
        "cross_species_conservation_check": [
            "ortholog context is absent or only weakly connected",
            "species divergence undermines the transfer argument",
        ],
    }
    return mapping.get(experiment, ["support is too weak to justify follow-up"])


def _blockers_for_step(step: dict[str, Any], species_report: dict[str, Any], plan_risks: list[dict[str, Any]]) -> list[str]:
    blockers = []
    layers = set(_required_layers(step["experiment"]))
    available = species_report.get("available_layers", {})
    for layer in layers:
        if available.get(layer, 0) <= 0:
            blockers.append(f"required layer missing: {layer}")
    for risk in plan_risks:
        if risk.get("scope") == step.get("gene_id") and risk.get("type") in ("weak_support", "narrow_followup"):
            blockers.append(risk["detail"])
    return blockers


def _decision_gates(lead_candidate: dict[str, Any], lead_plan: dict[str, Any], risk_flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gates = []
    confidence = lead_candidate.get("confidence", {}).get("label")
    gates.append({
        "gate": "lead_support_quality",
        "go": confidence in ("high", "moderate"),
        "detail": f"Lead candidate confidence is {confidence}.",
    })
    blockers = [r for r in risk_flags if r.get("scope") == lead_candidate.get("gene_id")]
    gates.append({
        "gate": "lead_blocker_review",
        "go": len(blockers) == 0,
        "detail": "No lead-specific blockers were identified." if not blockers else f"{len(blockers)} blocker(s) need review.",
    })
    gates.append({
        "gate": "has_actionable_experiment",
        "go": len(lead_plan.get("recommended_experiments", [])) > 0,
        "detail": "At least one actionable follow-up experiment is defined." if lead_plan.get("recommended_experiments") else "No actionable experiment was generated.",
    })
    return gates


def build_validation_plan(db, gene_ids: list[str], intent: str = "experiment",
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
    candidate_brief = brief.get("candidate_brief", [])
    experiment_brief = brief.get("experiment_brief", [])
    species_reports = {r["species"]: r for r in brief.get("species_readiness", [])}
    risk_flags = brief.get("risk_flags", [])

    validation_tracks = []
    for plan in experiment_brief:
        gene_id = plan["gene_id"]
        species_name = plan["species"]
        species_report = species_reports.get(species_name, {"available_layers": {}})
        for idx, exp in enumerate(plan.get("recommended_experiments", [])[:max_experiments], start=1):
            track = {
                "gene_id": gene_id,
                "symbol": plan.get("symbol"),
                "species": species_name,
                "rank": idx,
                "experiment": exp["experiment"],
                "priority_score": exp["priority_score"],
                "required_skills": exp.get("recommended_skills", []),
                "required_layers": _required_layers(exp["experiment"]),
                "objective": exp["rationale"],
                "success_criteria": _success_criteria(exp["experiment"], intent),
                "failure_signals": _failure_signals(exp["experiment"]),
            }
            track["blockers"] = _blockers_for_step(track, species_report, risk_flags)
            track["ready_to_run"] = len(track["blockers"]) == 0
            validation_tracks.append(track)

    lead_candidate = candidate_brief[0] if candidate_brief else None
    lead_plan = experiment_brief[0] if experiment_brief else {"recommended_experiments": []}

    checklist = []
    for i, step in enumerate(brief.get("workflow_plan", []), start=1):
        checklist.append({
            "step": i,
            "title": step["title"],
            "action": step["action"],
            "skills": step.get("skills", []),
            "completion_rule": f"finish '{step['action']}' and verify its output matches the brief intent",
        })

    summary = [
        "Validation plan built from the current research brief.",
        f"{len(validation_tracks)} validation track(s) were generated." if validation_tracks else "No validation tracks were generated.",
    ]
    if lead_candidate:
        summary.append(f"Lead candidate remains {lead_candidate.get('symbol') or lead_candidate.get('gene_id')}.")

    return {
        "title": f"Validation plan for {intent} follow-up",
        "intent": intent,
        "species": species,
        "lead_candidate": lead_candidate,
        "decision_gates": _decision_gates(lead_candidate or {}, lead_plan, risk_flags) if lead_candidate else [],
        "validation_tracks": validation_tracks,
        "execution_checklist": checklist,
        "risk_flags": risk_flags,
        "excluded_genes": brief.get("excluded_genes", []),
        "source_brief_summary": brief.get("executive_summary", []),
        "summary": summary,
    }
