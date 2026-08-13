"""Narrative study report generation for GRN Atlas workflows."""

from __future__ import annotations

from typing import Any

import packet


def _candidate_markdown(packet_data: dict[str, Any]) -> str:
    rows = ["| Gene | Species | TF | Score | Key evidence |", "|---|---|---:|---:|---|"]
    for candidate in packet_data.get("brief", {}).get("candidate_brief", []):
        evidence = candidate.get("evidence_summary", {}).get("sources", [])
        tf_flag = candidate.get("is_tf")
        if tf_flag is None:
            tf_flag = candidate.get("score_components", {}).get("tf", 0) > 0
        rows.append(
            f"| {candidate.get('symbol') or candidate.get('gene_id')} | "
            f"{candidate.get('species', 'n/a')} | "
            f"{'yes' if tf_flag else 'no'} | "
            f"{candidate.get('priority_score', candidate.get('score', 0)):.2f} | "
            f"{', '.join(evidence[:3]) if evidence else 'n/a'} |"
        )
    return "\n".join(rows) if len(rows) > 2 else "_No ranked candidates available._"


def _experiment_markdown(packet_data: dict[str, Any]) -> str:
    lines = []
    plans = packet_data.get("brief", {}).get("experiment_brief", [])
    for i, plan in enumerate(plans, start=1):
        exps = plan.get("recommended_experiments", [])
        lead = exps[0] if exps else {}
        lines.append(
            f"{i}. **{plan.get('symbol') or plan.get('gene_id')}** — "
            f"{lead.get('experiment', 'no_experiment')} — {lead.get('rationale', 'no rationale available')}"
        )
    return "\n".join(lines) if lines else "_No experiment recommendations available._"


def _validation_markdown(packet_data: dict[str, Any]) -> str:
    lines = []
    for track in packet_data.get("validation_plan", {}).get("validation_tracks", []):
        blockers = track.get("blockers", [])
        blocker_text = f" Blockers: {', '.join(b.rstrip('.') for b in blockers)}." if blockers else ""
        lines.append(
            f"- **{track.get('experiment')}** for {track.get('symbol') or track.get('gene_id')}: "
            f"{'ready' if track.get('ready_to_run') else 'not ready'}."
            f"{blocker_text}"
        )
    return "\n".join(lines) if lines else "_No validation tracks available._"


def _citations_markdown(packet_data: dict[str, Any]) -> str:
    sources = packet_data.get("citation_bundle", {}).get("sources", [])
    if not sources:
        return "_No citations selected._"
    lines = []
    for src in sources:
        citation = src.get("citation")
        if not citation:
            citation = "; ".join(
                str(part) for part in [src.get("authors"), src.get("year"), src.get("journal"), src.get("doi")] if part
            ) or "citation unavailable"
        lines.append(f"- **{src.get('name')}** ({src.get('version', 'n/a')}) — {citation}")
    return "\n".join(lines)


def _sectioned_markdown(report: dict[str, Any]) -> str:
    sections = report["report_sections"]
    uncertainty = sections.get("uncertainty_summary", [])
    strategy = sections.get("strategy_comparison")
    species_limits = sections.get("species_limitations", [])
    return "\n\n".join(
        [
            f"# {report['title']}",
            "## Executive summary\n" + "\n".join(f"- {item}" for item in sections["executive_summary"]),
            "## Lead candidate\n" + sections["lead_candidate"],
            "## Candidate ranking\n" + sections["candidate_table"],
            "## Recommended experiments\n" + sections["recommended_experiments"],
            "## Uncertainty boundary\n" + ("\n".join(f"- {item}" for item in uncertainty) if uncertainty else "_No uncertainty summary available._"),
            "## Strategy comparison\n" + (strategy if strategy else "_No strategy comparison available._"),
            "## Species limitations\n" + ("\n".join(f"- {item}" for item in species_limits) if species_limits else "_No species limitations recorded._"),
            "## Validation status\n" + sections["validation_status"],
            "## Collaborator handoff\n" + "\n".join(f"- {item}" for item in sections["handoff_checklist"]),
            "## Citations\n" + sections["citations"],
        ]
    ) + "\n"


def build_study_report(db, gene_ids: list[str], intent: str = "experiment",
                       species: str | None = None, max_candidates: int = 3,
                       max_experiments: int = 3) -> dict[str, Any]:
    packet_data = packet.build_study_packet(
        db,
        gene_ids,
        intent=intent,
        species=species,
        max_candidates=max_candidates,
        max_experiments=max_experiments,
    )
    lead = (packet_data.get("brief", {}).get("candidate_brief") or [{}])[0]
    report = {
        "title": f"Study report for {intent} follow-up",
        "intent": intent,
        "species": species,
        "packet": packet_data,
        "report_sections": {
            "executive_summary": packet_data.get("brief", {}).get("executive_summary", []),
            "lead_candidate": (
                f"{lead.get('symbol') or lead.get('gene_id')} "
                f"({lead.get('species', 'n/a')}) is the current lead candidate."
                if lead else "No lead candidate identified."
            ),
            "candidate_table": _candidate_markdown(packet_data),
            "recommended_experiments": _experiment_markdown(packet_data),
            "uncertainty_summary": packet_data.get("decision_boundary", {}).get("summary", [])
            or packet_data.get("decision_boundary", {}).get("summary", [])
            or packet_data.get("brief", {}).get("risk_flags", []),
            "strategy_comparison": (
                "\n".join(
                    f"- {item.get('strategy')}: {item.get('symbol') or item.get('gene_id')} "
                    f"(score {item.get('optimized_priority_score')})"
                    for item in (packet_data.get("strategy_comparison", {}).get("ranked_strategies", []))
                )
                or None
            ),
            "species_limitations": packet_data.get("species_limitations", []),
            "validation_status": _validation_markdown(packet_data),
            "handoff_checklist": packet_data.get("handoff", {}).get("handoff_checklist", []),
            "citations": _citations_markdown(packet_data),
        },
        "report_metadata": {
            "lead_candidate": packet_data.get("packet_metadata", {}).get("lead_candidate"),
            "workflow_steps": packet_data.get("packet_metadata", {}).get("workflow_steps", 0),
            "validation_tracks": packet_data.get("packet_metadata", {}).get("validation_tracks", 0),
            "citation_count": len(packet_data.get("citation_bundle", {}).get("source_keys", [])),
        },
    }
    report["markdown"] = _sectioned_markdown(report)
    return report
