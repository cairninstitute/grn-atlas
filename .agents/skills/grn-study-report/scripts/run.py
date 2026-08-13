#!/usr/bin/env python3
"""Build a collaborator-facing GRN Atlas study report."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common
import research_workflows as rw


def _postprocess(data, intent, species):
    packet = data.get("packet", {})
    data["audience_mode"] = packet.get("audience_mode", "collaborator_brief")
    data["methods_and_provenance_summary"] = packet.get("methods_and_provenance_summary", {})
    data["species_limitations_summary"] = packet.get("species_limitations", [])
    data["decision_summary"] = packet.get("decision_summary", {})
    report_sections = data.get("report_sections", {})
    report_sections["methods_and_provenance"] = (
        f"- direct_mode: {data['methods_and_provenance_summary'].get('direct_mode')}\n"
        f"- citation_source_count: {data['methods_and_provenance_summary'].get('citation_source_count')}"
    )
    report_sections["species_limitations_summary"] = "\n".join(
        f"- {item}" for item in data["species_limitations_summary"]
    ) or "_No species limitations recorded._"
    data["report_sections"] = report_sections
    return data


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas study report")
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
        data = common.http_post(args.http, "/api/v1/research/study-report", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.StudyReportRequest(**payload)
        data = common.run_async(backend.study_report(req))

    if not args.http:
        data.update(resolution)
    common.output(_postprocess(data, args.intent, args.species))


if __name__ == "__main__":
    main()
