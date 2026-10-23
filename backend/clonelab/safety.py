"""Deterministic scope checks for CloneLab inputs."""

from __future__ import annotations


def assess_scope(*, total_bases: int, max_bases: int, organism: str | None = None,
                 metadata: dict | None = None) -> dict:
    reasons = []
    if total_bases > max_bases:
        reasons.append(f"sequence total exceeds configured limit of {max_bases} bases")
    metadata = metadata or {}
    if metadata.get("pathogenic") is True or metadata.get("regulated_agent") is True:
        reasons.append("metadata requires institutional biosafety review")
    return {
        "allowed": not reasons,
        "review_required": bool(reasons),
        "reasons": reasons,
        "organism": organism,
        "policy": "clonelab_research_scope_v1",
    }
