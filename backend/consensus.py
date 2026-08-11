"""Consensus ranking and counterfactual analysis for GRN Atlas."""

from __future__ import annotations

from typing import Any

import evidence
import hypothesis
import literature
import planning


def _consensus_components(db, candidate: dict[str, Any], include_external: bool, years_back: int) -> dict[str, float]:
    components = dict(candidate.get("score_components", {}))
    components.setdefault("confidence", {"low": 0.25, "moderate": 0.6, "high": 0.9}.get(candidate.get("confidence", {}).get("label"), 0.4))
    components.setdefault("priority", candidate.get("priority_score", 0.0))
    if include_external:
        ext = literature.review_literature(
            db,
            scope="gene",
            gene_id=candidate["gene_id"],
            years_back=years_back,
            max_results=5,
        )
        support = ext.get("summary", {}).get("support", 0)
        contradict = ext.get("summary", {}).get("contradict", 0)
        components["external_support"] = min(support / 3.0, 1.0)
        components["external_contradiction"] = min(contradict / 3.0, 1.0)
    else:
        components["external_support"] = 0.0
        components["external_contradiction"] = 0.0
    return components


def rank_consensus(db, gene_ids: list[str], intent: str = "experiment", species: str | None = None,
                   top_n: int = 10, include_external: bool = False, years_back: int = 5) -> dict[str, Any]:
    triage = planning.triage_candidates(db, gene_ids, intent=intent, species=species, top_n=top_n)
    ranked = []
    for cand in triage.get("ranked_candidates", []):
        comps = _consensus_components(db, cand, include_external, years_back)
        consensus_score = (
            0.35 * cand.get("priority_score", 0.0)
            + 0.15 * comps.get("curated", 0.0)
            + 0.10 * comps.get("expression", 0.0)
            + 0.10 * comps.get("motif", 0.0)
            + 0.10 * comps.get("orthology", 0.0)
            + 0.10 * comps.get("readiness", 0.0)
            + 0.10 * comps.get("external_support", 0.0)
            - 0.10 * comps.get("external_contradiction", 0.0)
        )
        audit = evidence.summarize_gene_evidence(db, cand["gene_id"])
        ranked.append({
            "gene_id": cand["gene_id"],
            "symbol": cand.get("symbol"),
            "species": cand.get("species"),
            "consensus_score": round(max(min(consensus_score, 1.0), 0.0), 3),
            "priority_score": cand.get("priority_score"),
            "confidence": cand.get("confidence"),
            "score_components": comps,
            "reasons": cand.get("reasons", [])[:4],
            "coverage_gaps": cand.get("coverage_gaps", []),
            "evidence_summary": audit.get("evidence_summary", {}),
        })
    ranked.sort(key=lambda r: (-r["consensus_score"], -r["priority_score"], r["symbol"] or r["gene_id"]))
    return {
        "intent": intent,
        "species": species,
        "include_external": include_external,
        "ranked_candidates": ranked[:top_n],
        "excluded_genes": triage.get("excluded_genes", []),
    }


def counterfactual_analysis(db, gene_ids: list[str], intent: str = "experiment",
                            species: str | None = None, include_external: bool = False,
                            years_back: int = 5) -> dict[str, Any]:
    comparison = hypothesis.compare_hypotheses(db, gene_ids, intent=intent, species=species)
    consensus_rank = rank_consensus(
        db,
        gene_ids,
        intent=intent,
        species=species,
        top_n=max(len(gene_ids), 2),
        include_external=include_external,
        years_back=years_back,
    )
    ranked = consensus_rank.get("ranked_candidates", [])
    winner = ranked[0] if ranked else None
    runner_up = ranked[1] if len(ranked) > 1 else None
    overturn_conditions = []
    if winner and runner_up:
        for factor in ("curated", "expression", "motif", "orthology", "readiness", "external_support"):
            w = winner.get("score_components", {}).get(factor, 0.0)
            r = runner_up.get("score_components", {}).get(factor, 0.0)
            if w > r:
                overturn_conditions.append(
                    f"additional {factor} support for {runner_up['symbol'] or runner_up['gene_id']} or loss of the same support for {winner['symbol'] or winner['gene_id']} would reduce the gap"
                )
        if winner.get("score_components", {}).get("external_contradiction", 0.0) == 0 and include_external:
            overturn_conditions.append(
                f"credible contradictory literature against {winner['symbol'] or winner['gene_id']} would materially weaken the current lead"
            )
    return {
        "intent": intent,
        "species": species,
        "include_external": include_external,
        "consensus_ranking": consensus_rank,
        "hypothesis_comparison": comparison,
        "winner": winner,
        "runner_up": runner_up,
        "overturn_conditions": overturn_conditions[:5],
        "minimum_flip_requirements": overturn_conditions[:2],
        "summary": [
            f"Current consensus lead is {winner.get('symbol') or winner.get('gene_id')}." if winner else "No consensus lead identified.",
            f"Runner-up is {runner_up.get('symbol') or runner_up.get('gene_id')}." if runner_up else "No runner-up available.",
            "Counterfactual analysis highlights the smallest evidence shifts likely to change the ranking.",
        ],
    }
