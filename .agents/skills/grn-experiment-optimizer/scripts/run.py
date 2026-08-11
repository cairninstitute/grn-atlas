#!/usr/bin/env python3
"""Constraint-aware experiment optimization."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


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

    payload = {
        "gene_ids": [g.strip() for g in args.gene_ids.split(",") if g.strip()],
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

    common.output(data)


if __name__ == "__main__":
    main()
