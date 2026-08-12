"""Constraint-aware experiment optimization for GRN Atlas."""

from __future__ import annotations

from typing import Any

import planning


_EXPERIMENT_METADATA = {
    "network_perturbation": {"cost": 2, "time": 2, "assay": "in_silico"},
    "expression_context_review": {"cost": 1, "time": 1, "assay": "expression"},
    "motif_binding_validation": {"cost": 2, "time": 2, "assay": "motif"},
    "dsrna_design": {"cost": 2, "time": 2, "assay": "rnai"},
    "trait_association_followup": {"cost": 1, "time": 1, "assay": "trait"},
    "cross_species_conservation_check": {"cost": 1, "time": 1, "assay": "comparative"},
}

_BUDGET_CAP = {"low": 1, "medium": 2, "high": 3}


def _constraint_adjustment(exp: dict[str, Any], budget_level: str | None,
                           timeline_days: int | None, allowed_assays: list[str] | None) -> tuple[float, list[str]]:
    meta = _EXPERIMENT_METADATA.get(exp["experiment"], {"cost": 2, "time": 2, "assay": "general"})
    score = exp["priority_score"]
    notes = []
    if budget_level:
        cap = _BUDGET_CAP.get(budget_level, 2)
        if meta["cost"] > cap:
            score -= 0.18 * (meta["cost"] - cap)
            notes.append(f"penalized for {budget_level} budget")
        elif meta["cost"] <= cap:
            score += 0.03
    if timeline_days is not None:
        if meta["time"] > timeline_days:
            score -= 0.20
            notes.append("penalized for timeline")
        elif meta["time"] <= max(timeline_days, 1):
            score += 0.02
    if allowed_assays:
        if meta["assay"] not in allowed_assays:
            score -= 0.35
            notes.append("outside allowed assay classes")
        else:
            score += 0.04
    return round(max(min(score, 0.99), 0.0), 3), notes


def optimize_experiments(db, gene_ids: list[str], intent: str = "experiment",
                         species: str | None = None, budget_level: str | None = None,
                         timeline_days: int | None = None, allowed_assays: list[str] | None = None,
                         max_recommendations: int = 5) -> dict[str, Any]:
    base = planning.prioritize_experiments(
        db,
        gene_ids,
        intent=intent,
        species=species,
        max_recommendations=max_recommendations,
    )
    ranked = []
    for plan in base.get("plans", []):
        for exp in plan.get("recommended_experiments", []):
            adjusted, notes = _constraint_adjustment(exp, budget_level, timeline_days, allowed_assays)
            meta = _EXPERIMENT_METADATA.get(exp["experiment"], {"cost": 2, "time": 2, "assay": "general"})
            ranked.append({
                "gene_id": plan["gene_id"],
                "symbol": plan["symbol"],
                "label": plan.get("label") or plan["symbol"] or plan["gene_id"],
                "label_inferred": bool(plan.get("label_inferred", False)),
                "species": plan["species"],
                "experiment": exp["experiment"],
                "base_priority_score": exp["priority_score"],
                "optimized_priority_score": adjusted,
                "assay_class": meta["assay"],
                "cost_tier": meta["cost"],
                "time_tier_days": meta["time"],
                "rationale": exp["rationale"],
                "recommended_skills": exp.get("recommended_skills", []),
                "constraint_notes": notes,
            })
    ranked.sort(key=lambda r: (-r["optimized_priority_score"], -r["base_priority_score"], r["experiment"], r["gene_id"]))
    warnings = []
    if not ranked:
        warnings.append("no experiment recommendations were available for the provided genes")
    if budget_level == "low":
        warnings.append("low-budget mode favors in-silico, expression, and comparative checks over wet-lab follow-up")
    if timeline_days is not None and timeline_days <= 1:
        warnings.append("very short timelines may exclude wet-lab-style follow-up from the top of the ranking")
    return {
        "intent": intent,
        "species": species,
        "budget_level": budget_level,
        "timeline_days": timeline_days,
        "allowed_assays": allowed_assays or [],
        "candidate_count": len(base.get("plans", [])),
        "ranked_experiments": ranked[:max_recommendations],
        "excluded_genes": base.get("excluded_genes", []),
        "warnings": warnings,
    }
