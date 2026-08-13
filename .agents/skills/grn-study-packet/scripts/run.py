#!/usr/bin/env python3
"""Build a shareable GRN Atlas study packet."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common
import research_workflows as rw


def _audience_mode(intent: str) -> str:
    if intent == "rnai":
        return "lab_handoff"
    if intent == "experiment":
        return "decision_memo"
    return "collaborator_brief"


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas study packet")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs")
    parser.add_argument("--intent", default="experiment")
    parser.add_argument("--species")
    parser.add_argument("--max-candidates", type=int, default=3)
    parser.add_argument("--max-experiments", type=int, default=3)
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
        "max_candidates": args.max_candidates,
        "max_experiments": args.max_experiments,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/research/study-packet", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.StudyPacketRequest(**payload)
        data = common.run_async(backend.study_packet(req))

    if not args.http:
        data.update(resolution)
        backend = rw.get_backend()
        data["decision_boundary"] = common.run_async(
            backend.confidence_boundary(
                backend.ConfidenceBoundaryRequest(
                    gene_ids=gene_ids,
                    intent=args.intent,
                    species=args.species,
                    max_candidates=args.max_candidates,
                    max_experiments=args.max_experiments,
                )
            )
        ) if gene_ids else None
        optimized = common.run_async(
            backend.experiment_optimize(
                backend.ExperimentOptimizeRequest(
                    gene_ids=gene_ids,
                    intent=args.intent,
                    species=args.species,
                    budget_level="medium",
                    timeline_days=14,
                    allowed_assays=[],
                    max_recommendations=5,
                )
            )
        ) if gene_ids else {"ranked_experiments": []}
        data["strategy_comparison"] = rw.build_experiment_strategy_summary(optimized.get("ranked_experiments", []))
        data["species_limitations"] = (
            (data.get("decision_boundary") or {}).get("brief", {}).get("risk_flags", [])
            if data.get("decision_boundary") else []
        )
        data["execution_design"] = rw.build_execution_design(
            args.intent,
            args.species,
            (data.get("strategy_comparison") or {}).get("ranked_strategies", []),
        )
        data["audience_mode"] = _audience_mode(args.intent)
        data["methods_and_provenance_summary"] = {
            "direct_mode": True,
            "citation_source_count": len((data.get("citation_bundle") or {}).get("source_keys", [])),
            "freshness_checked": (data.get("freshness_summary") or {}).get("checked"),
        }
        data["decision_summary"] = {
            "lead_candidate": (data.get("packet_metadata") or {}).get("lead_candidate"),
            "primary_strategy": (data.get("execution_design") or {}).get("primary_strategy"),
            "main_uncertainties": data.get("species_limitations", [])[:3],
        }
        data["handoff_variants"] = {
            "lab_handoff": ["execution_design", "validation_plan", "decision_boundary"],
            "decision_memo": ["decision_summary", "strategy_comparison", "species_limitations"],
        }
    common.output(data)


if __name__ == "__main__":
    main()
