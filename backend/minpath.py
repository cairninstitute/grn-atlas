"""Minimal validation path generation for GRN Atlas workflows."""

from __future__ import annotations

from typing import Any

import validation


def build_minimal_validation_path(db, gene_ids: list[str], intent: str = "experiment",
                                  species: str | None = None, max_candidates: int = 3,
                                  max_experiments: int = 3) -> dict[str, Any]:
    plan = validation.build_validation_plan(
        db,
        gene_ids,
        intent=intent,
        species=species,
        max_candidates=max_candidates,
        max_experiments=max_experiments,
    )
    tracks = plan.get("validation_tracks", [])
    lead = plan.get("lead_candidate")
    ranked = sorted(tracks, key=lambda row: (bool(row.get("blockers")), -row.get("priority_score", 0.0), row.get("rank", 999)))
    first = ranked[0] if ranked else None
    alternatives = [t for t in ranked[1:3]]
    blockers = list(dict.fromkeys((first or {}).get("blockers", [])))
    prerequisite_checks = [
        f"confirm {lead.get('symbol') or lead.get('gene_id')} is still the lead candidate for the current question"
    ] if lead else []
    prerequisite_checks.extend((first or {}).get("required_layers", []))
    stop_go = [
        {"decision": "go", "rule": rule} for rule in (first or {}).get("success_criteria", [])[:2]
    ] + [
        {"decision": "stop", "rule": rule} for rule in (first or {}).get("failure_signals", [])[:2]
    ]
    escalation = []
    if blockers:
        escalation.append("resolve the current blockers before treating the first-step result as decision-grade evidence")
    if alternatives:
        escalation.append(f"if the first step fails, switch to {alternatives[0].get('experiment')} as the next cheapest defensible track")
    if not escalation:
        escalation.append("if the first step is inconclusive, widen the evidence base with orthogonal validation rather than repeating the same assay")

    return {
        "title": f"Minimal validation path for {intent} follow-up",
        "intent": intent,
        "species": species,
        "validation_plan": plan,
        "lead_candidate": lead,
        "minimal_first_step": first,
        "prerequisite_checks": prerequisite_checks,
        "current_blockers": blockers,
        "stop_go_gates": stop_go,
        "fallback_alternatives": alternatives,
        "escalation_path": escalation,
        "summary": [
            f"Lead candidate is {lead.get('symbol') or lead.get('gene_id')}." if lead else "No lead candidate identified.",
            f"Minimal first step is {(first or {}).get('experiment')}." if first else "No validation step could be identified.",
            f"{len(blockers)} blocker(s) currently constrain the first step.",
        ],
    }
