"""Hypothesis comparison for GRN Atlas research workflows."""

from __future__ import annotations

from itertools import combinations
from typing import Any

import briefing


def _component_deltas(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    deltas = []
    for key in ("curated", "motif", "expression", "pathway", "trait", "orthology", "tf", "readiness"):
        av = a.get("score_components", {}).get(key, 0.0)
        bv = b.get("score_components", {}).get(key, 0.0)
        diff = round(av - bv, 3)
        if abs(diff) >= 0.05:
            deltas.append({"factor": key, "winner_value": av, "loser_value": bv, "delta": diff})
    deltas.sort(key=lambda row: -abs(row["delta"]))
    return deltas


def _decisive_factors(winner: dict[str, Any], runner_up: dict[str, Any]) -> list[str]:
    messages = []
    for row in _component_deltas(winner, runner_up)[:4]:
        relation = "stronger" if row["delta"] > 0 else "weaker"
        messages.append(
            f"{winner.get('symbol') or winner.get('gene_id')} has {relation} {row['factor']} support "
            f"than {runner_up.get('symbol') or runner_up.get('gene_id')} (Δ={row['delta']})."
        )
    if winner.get("confidence", {}).get("label") != runner_up.get("confidence", {}).get("label"):
        messages.append(
            f"confidence differs: {winner.get('symbol') or winner.get('gene_id')} is "
            f"{winner.get('confidence', {}).get('label')} vs {runner_up.get('confidence', {}).get('label')}."
        )
    return messages


def _overturn_conditions(winner: dict[str, Any], runner_up: dict[str, Any]) -> list[str]:
    conditions = []
    for factor in ("curated", "expression", "motif", "readiness", "trait", "orthology"):
        win = winner.get("score_components", {}).get(factor, 0.0)
        lose = runner_up.get("score_components", {}).get(factor, 0.0)
        if win > lose:
            conditions.append(
                f"new {factor} support for {runner_up.get('symbol') or runner_up.get('gene_id')} "
                f"or loss of {factor} support for {winner.get('symbol') or winner.get('gene_id')} would narrow the gap."
            )
    if winner.get("priority_score", 0.0) - runner_up.get("priority_score", 0.0) < 0.1:
        conditions.append("the current margin is narrow enough that one strong orthogonal evidence layer could change the lead.")
    return conditions[:4] or ["no obvious overturn condition was identified from current atlas evidence."]


def compare_hypotheses(db, gene_ids: list[str], intent: str = "experiment",
                       species: str | None = None, max_candidates: int = 5,
                       max_experiments: int = 3) -> dict[str, Any]:
    brief = briefing.build_research_brief(
        db,
        gene_ids,
        intent=intent,
        species=species,
        max_candidates=max_candidates,
        max_experiments=max_experiments,
    )
    candidates = brief.get("candidate_brief", [])
    plans_by_gene = {p["gene_id"]: p for p in brief.get("experiment_brief", [])}

    pairwise = []
    for a, b in combinations(candidates, 2):
        winner, loser = (a, b) if a.get("priority_score", 0.0) >= b.get("priority_score", 0.0) else (b, a)
        pairwise.append({
            "winner_gene_id": winner["gene_id"],
            "loser_gene_id": loser["gene_id"],
            "margin": round(winner.get("priority_score", 0.0) - loser.get("priority_score", 0.0), 3),
            "decisive_factors": _decisive_factors(winner, loser),
        })

    winner = candidates[0] if candidates else None
    runner_up = candidates[1] if len(candidates) > 1 else None
    comparison_table = []
    for candidate in candidates:
        lead_exp = plans_by_gene.get(candidate["gene_id"], {}).get("recommended_experiments", [{}])[0]
        comparison_table.append({
            "gene_id": candidate["gene_id"],
            "symbol": candidate.get("symbol"),
            "species": candidate.get("species"),
            "priority_score": candidate.get("priority_score"),
            "confidence": candidate.get("confidence", {}).get("label"),
            "lead_experiment": lead_exp.get("experiment"),
            "top_reasons": candidate.get("reasons", [])[:3],
        })

    return {
        "title": f"Hypothesis comparison for {intent} follow-up",
        "intent": intent,
        "species": species,
        "brief": brief,
        "winner": winner,
        "runner_up": runner_up,
        "comparison_table": comparison_table,
        "pairwise_comparisons": pairwise,
        "decisive_factors": _decisive_factors(winner, runner_up) if winner and runner_up else [],
        "overturn_conditions": _overturn_conditions(winner, runner_up) if winner and runner_up else [],
        "summary": [
            f"Current lead hypothesis is {winner.get('symbol') or winner.get('gene_id')}." if winner else "No lead hypothesis identified.",
            f"Runner-up is {runner_up.get('symbol') or runner_up.get('gene_id')}." if runner_up else "No runner-up was available for comparison.",
            f"{len(pairwise)} pairwise comparison(s) were generated from the current candidate set.",
        ],
    }
