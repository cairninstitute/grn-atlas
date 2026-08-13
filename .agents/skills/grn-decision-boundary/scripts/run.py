#!/usr/bin/env python3
"""Uncertainty-aware decision summary."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common
import research_workflows as rw


def _extract_overturn_conditions(counterfactual: dict) -> list[str]:
    out = []
    for item in counterfactual.get("overturn_conditions", []):
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            text = item.get("condition") or item.get("summary") or item.get("reason")
            if text:
                out.append(text)
    return out


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas decision boundary")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs or symbols")
    parser.add_argument("--intent", default="experiment")
    parser.add_argument("--species")
    parser.add_argument("--max-candidates", type=int, default=3)
    parser.add_argument("--max-experiments", type=int, default=3)
    args = parser.parse_args()

    raw_genes = [g.strip() for g in args.gene_ids.split(",") if g.strip()]

    if args.http:
        resolved = [{"input": g, "gene_id": g, "symbol": g, "species": args.species} for g in raw_genes]
        gene_ids = raw_genes
        unresolved = []
    else:
        resolved, unresolved = rw.resolve_gene_ids(raw_genes, args.species)
        gene_ids = [g["gene_id"] for g in resolved]
    if not gene_ids:
        common.output({"error": "No genes resolved for decision boundary analysis", "unresolved_inputs": unresolved, "status_code": 404})
        return

    backend = rw.get_backend()
    payload = dict(
        gene_ids=gene_ids,
        intent=args.intent,
        species=args.species,
        max_candidates=args.max_candidates,
        max_experiments=args.max_experiments,
    )
    if args.http:
        confidence = common.http_post(args.http, "/api/v1/research/confidence-boundary", payload)
        minimal = common.http_post(args.http, "/api/v1/research/minimal-validation", payload)
        counterfactual = common.http_post(args.http, "/api/v1/research/counterfactual-analysis", {**payload, "include_external": False, "years_back": 5})
    else:
        confidence = common.run_async(backend.confidence_boundary(backend.ConfidenceBoundaryRequest(**payload)))
        minimal = common.run_async(backend.minimal_validation(backend.MinimalValidationRequest(**payload)))
        counterfactual = common.run_async(backend.counterfactual_analysis(backend.CounterfactualAnalysisRequest(**payload, include_external=False, years_back=5)))

    brief = confidence.get("brief", {}) if isinstance(confidence, dict) else {}
    supported_now = confidence.get("summary", []) if isinstance(confidence, dict) else []
    unsupported_now = brief.get("risk_flags", []) if isinstance(brief, dict) else []
    ambiguous_now = []
    for candidate in brief.get("candidate_brief", []):
        ambiguous_now.extend(candidate.get("coverage_gaps", []))
    output = {
        "title": f"Decision boundary for {args.intent} follow-up",
        "intent": args.intent,
        "species": args.species,
        "resolved_genes": resolved,
        "unresolved_inputs": unresolved,
        "supported_now": supported_now,
        "unsupported_now": unsupported_now,
        "ambiguous_now": ambiguous_now,
        "overturn_conditions": _extract_overturn_conditions(counterfactual),
        "smallest_next_validation_move": minimal.get("minimal_first_step"),
        "prerequisite_checks": minimal.get("prerequisite_checks", []),
        "fallback_alternatives": minimal.get("fallback_alternatives", []),
        "counterfactual_summary": counterfactual.get("summary", []),
        "confidence_boundary": confidence,
        "minimal_validation": minimal,
    }
    common.output(output)


if __name__ == "__main__":
    main()
