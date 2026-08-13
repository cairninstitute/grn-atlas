#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def _postprocess(data):
    data["readiness_category"] = "supported" if data.get("supported") else "blocked"
    data["missing_layer_taxonomy"] = [
        {"layer": layer, "reason": "required_for_trajectory_workflow"} for layer in data.get("required_layers", [])
    ]
    data["actionable_readiness_summary"] = {
        "supported": data.get("supported"),
        "reason": data.get("reason"),
        "smallest_next_data_move": (data.get("recommended_next_steps") or [None])[0],
    }
    data["onboarding_priority_layers"] = data.get("required_layers", [])
    data["minimal_dataset_requirements"] = [
        "ordered time-series or pseudotime matrix",
        "trajectory stage annotations",
        "stage-specific regulatory relationships",
    ]
    data["readiness_to_analysis_gap"] = len(data.get("required_layers", []))
    data["future_enabled_workflows"] = [
        "trajectory-stage upstream analysis",
        "time-varying regulon shifts",
        "trajectory-aware perturbation prioritization",
    ]
    return data


def main():
    parser = argparse.ArgumentParser(description="Trajectory regulation readiness")
    common.add_common_args(parser)
    parser.add_argument("--species", required=True)
    parser.add_argument("--gene-ids")
    args = parser.parse_args()
    payload = {"species": args.species, "gene_ids": [g.strip() for g in args.gene_ids.split(",")] if args.gene_ids else None}
    if args.http:
        data = common.http_post(args.http, "/api/v1/trajectory/regulation", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.trajectory_regulation(backend.TrajectoryRegulationRequest(**payload)))
    common.output(_postprocess(data))


if __name__ == "__main__":
    main()
