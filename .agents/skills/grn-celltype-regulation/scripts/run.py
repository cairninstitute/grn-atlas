#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def _postprocess(data):
    data["readiness_category"] = "supported" if data.get("supported") else "blocked"
    data["missing_layer_taxonomy"] = [
        {"layer": layer, "reason": "required_for_celltype_workflow"} for layer in data.get("required_layers", [])
    ]
    data["actionable_readiness_summary"] = {
        "supported": data.get("supported"),
        "reason": data.get("reason"),
        "smallest_next_data_move": (data.get("recommended_next_steps") or [None])[0],
    }
    data["onboarding_priority_layers"] = data.get("required_layers", [])
    data["minimal_dataset_requirements"] = [
        "cell-level expression matrix",
        "cell annotations",
        "cell-type-resolved regulatory edges",
    ]
    data["readiness_to_analysis_gap"] = len(data.get("required_layers", []))
    data["future_enabled_workflows"] = [
        "cell-type-specific upstream analysis",
        "cell-state differential regulation",
        "cell-type regulon prioritization",
    ]
    return data


def main():
    parser = argparse.ArgumentParser(description="Cell-type regulation readiness")
    common.add_common_args(parser)
    parser.add_argument("--species", required=True)
    parser.add_argument("--gene-ids")
    args = parser.parse_args()
    payload = {"species": args.species, "gene_ids": [g.strip() for g in args.gene_ids.split(",")] if args.gene_ids else None}
    if args.http:
        data = common.http_post(args.http, "/api/v1/celltype/regulation", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.celltype_regulation(backend.CelltypeRegulationRequest(**payload)))
    common.output(_postprocess(data))


if __name__ == "__main__":
    main()
