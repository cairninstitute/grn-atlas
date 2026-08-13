#!/usr/bin/env python3
"""Constraint-aware experiment optimization."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common
import research_workflows as rw


def _postprocess(data):
    ranked = data.get("ranked_experiments", [])
    data["strategy_comparison"] = rw.build_experiment_strategy_summary(ranked)
    data["recommended_first_action"] = data["strategy_comparison"].get("recommended_first_action")
    data["fallback_action"] = data["strategy_comparison"].get("fallback_action")
    data["execution_design"] = rw.build_execution_design(
        data.get("intent"),
        data.get("species"),
        data["strategy_comparison"].get("ranked_strategies", []),
    )
    return data


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas experiment optimizer")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs")
    parser.add_argument("--intent", default="experiment")
    parser.add_argument("--species")
    parser.add_argument("--budget-level", choices=["low", "medium", "high"])
    parser.add_argument("--timeline-days", type=int, default=None)
    parser.add_argument("--allowed-assays", default=None, help="Comma-separated assay classes")
    parser.add_argument("--max-recommendations", type=int, default=5)
    args = parser.parse_args()

    raw_gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()]
    if args.http:
        gene_ids = raw_gene_ids
        resolution = {"resolved_genes": [], "unresolved_inputs": []}
    else:
        resolved, unresolved = rw.resolve_gene_ids(raw_gene_ids, args.species)
        gene_ids = [g["gene_id"] for g in resolved]
        resolution = {"resolved_genes": resolved, "unresolved_inputs": unresolved}
    payload = {
        "gene_ids": gene_ids,
        "intent": args.intent,
        "species": args.species,
        "budget_level": args.budget_level,
        "timeline_days": args.timeline_days,
        "allowed_assays": [a.strip() for a in args.allowed_assays.split(",") if a.strip()] if args.allowed_assays else [],
        "max_recommendations": args.max_recommendations,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/experiments/optimize", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.experiment_optimize(backend.ExperimentOptimizeRequest(**payload)))

    if not args.http:
        data.update(resolution)
    common.output(_postprocess(data))


if __name__ == "__main__":
    main()
