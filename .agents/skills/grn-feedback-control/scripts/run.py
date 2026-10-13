#!/usr/bin/env python3
"""Discover bounded feedback circuits and structural controller candidates."""

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Species-wide signed feedback/control analysis")
    common.add_common_args(parser)
    parser.add_argument("--species", required=True)
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--evidence-tiers", default="measured,perturbation")
    parser.add_argument("--max-loop-length", type=int, default=6)
    parser.add_argument("--max-cores", type=int, default=50)
    parser.add_argument("--max-circuits", type=int, default=100)
    parser.add_argument("--circuits-per-core", type=int, default=12)
    parser.add_argument("--max-search-states", type=int, default=100_000)
    parser.add_argument("--max-controllers", type=int, default=30)
    parser.add_argument("--max-systems", type=int, default=20)
    parser.add_argument("--max-system-genes", type=int, default=80)
    parser.add_argument("--topology-only", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    payload = {
        "species": args.species,
        "min_confidence": args.min_confidence,
        "evidence_tiers": [tier.strip() for tier in args.evidence_tiers.split(",") if tier.strip()],
        "max_loop_length": args.max_loop_length,
        "max_cores": args.max_cores,
        "max_circuits": args.max_circuits,
        "circuits_per_core": args.circuits_per_core,
        "max_search_states": args.max_search_states,
        "max_controllers": args.max_controllers,
        "max_systems": args.max_systems,
        "max_system_genes": args.max_system_genes,
        "discover_systems": not args.topology_only,
        "refresh": args.refresh,
    }
    if args.http:
        result = common.http_post(args.http, "/api/v1/network/feedback-control", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import feedback_control
        import main as backend

        params = feedback_control.FeedbackParameters(
            min_confidence=args.min_confidence,
            evidence_tiers=tuple(payload["evidence_tiers"]),
            max_loop_length=args.max_loop_length,
            max_cores=args.max_cores,
            max_circuits=args.max_circuits,
            circuits_per_core=args.circuits_per_core,
            max_search_states=args.max_search_states,
            max_controllers=args.max_controllers,
            max_systems=args.max_systems,
            max_system_genes=args.max_system_genes,
            discover_systems=not args.topology_only,
        )
        store = feedback_control.FeedbackStore(
            backend.DATA_DIR / "feedback_analysis.sqlite3"
        )
        result = feedback_control.analyze_and_store(
            backend.db.conn, store, backend._normalize_species_input(args.species), params,
            refresh=args.refresh,
        )
    common.output(result)


if __name__ == "__main__":
    main()
