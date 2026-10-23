"""Reproducible CloneLab report exports."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime


def export_report(project: dict, analysis: dict, *, output_format: str = "json") -> dict:
    payload = {
        "schema": "clonelab-report-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "project": project,
        "analysis": analysis,
        "claim_boundary": "Predictions are computational analyses, not experimental observations or sequence confirmation.",
    }
    if output_format == "json":
        content = json.dumps(payload, indent=2, sort_keys=True)
        media_type = "application/json"
    elif output_format == "markdown":
        content = _markdown(payload)
        media_type = "text/markdown"
    else:
        raise ValueError("output_format must be json or markdown")
    return {
        "format": output_format,
        "media_type": media_type,
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
    }


def _markdown(payload: dict) -> str:
    project = payload["project"]
    return "\n".join([
        f"# CloneLab Report: {project.get('name', 'Untitled project')}",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Project",
        "",
        f"- Project ID: `{project.get('project_id', 'stateless')}`",
        f"- Description: {project.get('description') or 'Not provided'}",
        "",
        "## Deterministic Analysis",
        "",
        "```json",
        json.dumps(payload["analysis"], indent=2, sort_keys=True),
        "```",
        "",
        "## Interpretation Boundary",
        "",
        payload["claim_boundary"],
        "",
    ])
