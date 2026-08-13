#!/usr/bin/env python3
"""Assess GRN Atlas cross-species transferability."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common
import research_workflows as rw


def _postprocess(data):
    ortholog_found = bool(data.get("best_target_ortholog") or data.get("ortholog_candidates"))
    readiness = (data.get("target_readiness") or {}).get("readiness_score", 0.0) or 0.0
    safe = []
    unsafe = []
    missing = []
    if readiness >= 0.8:
        safe.append(f"{data.get('target_species')} has the core layers required for {data.get('intent')} analysis.")
    else:
        unsafe.append(f"{data.get('target_species')} lacks enough atlas support for a confident {data.get('intent')} transfer.")
    if ortholog_found:
        safe.append("at least one target-species ortholog candidate is available for follow-up")
    else:
        unsafe.append("no target-species ortholog is currently mapped for this source gene")
        missing.append("ortholog or direct target-species gene mapping")
    if (data.get("transferability_score") or 0.0) < 0.5:
        missing.append("gene-level support stronger than generic species-layer readiness")
    exact_ortholog_support = {
        "supported": ortholog_found,
        "best_target_ortholog": data.get("best_target_ortholog"),
        "ortholog_candidate_count": len(data.get("ortholog_candidates") or []),
    }
    family_analogs = rw.family_level_analogs(
        data.get("target_species"),
        (data.get("source_gene") or {}).get("symbol"),
    )
    data["transfer_modes_considered"] = ["exact_ortholog", "family_level_analog", "species_layer_readiness"]
    data["exact_ortholog_support"] = exact_ortholog_support
    data["family_level_analog_candidates"] = family_analogs
    data["best_available_analogs"] = family_analogs[:3]
    data["unsupported_extrapolations"] = [
        "direct edge conservation without ortholog support"
    ] if not ortholog_found else []
    data["safe_to_infer"] = safe
    data["unsafe_to_infer"] = unsafe
    data["missing_for_confident_transfer"] = missing
    return data


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas transferability assessment")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True)
    parser.add_argument("--target-species", required=True)
    parser.add_argument("--intent", default="experiment")
    args = parser.parse_args()

    payload = {
        "gene_id": args.gene_id,
        "target_species": args.target_species,
        "intent": args.intent,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/research/transferability", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.TransferabilityRequest(**payload)
        data = common.run_async(backend.transferability_assessment(req))

    common.output(_postprocess(data))


if __name__ == "__main__":
    main()
