"""Shared CLI adapter for CloneLab AgentSkills."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_grn-common" / "scripts"))
import common


def _json(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def run(action):
    parser = argparse.ArgumentParser(description=f"Darwin CloneLab {action}")
    common.add_common_args(parser)
    parser.add_argument("--sequence")
    parser.add_argument("--content")
    parser.add_argument("--topology", choices=("linear", "circular"), default="circular")
    parser.add_argument("--enzymes", default="")
    parser.add_argument("--vector")
    parser.add_argument("--insert")
    parser.add_argument("--insertion-start", type=int, default=0)
    parser.add_argument("--hypotheses", type=_json)
    parser.add_argument("--fragments", type=_json)
    parser.add_argument("--observed", type=_json)
    parser.add_argument("--predictions", type=_json)
    parser.add_argument("--project", type=_json)
    parser.add_argument("--analysis", type=_json)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    enzymes = [value.strip() for value in args.enzymes.split(",") if value.strip()]
    if args.http:
        result = _http(action, args, enzymes)
    else:
        backend = Path(__file__).resolve().parents[4] / "backend"
        sys.path.insert(0, str(backend))
        result = _direct(action, args, enzymes)
    common.output(result)


def _direct(action, args, enzymes):
    if action == "sequence":
        from clonelab.formats import parse_sequences
        return {"sequences": parse_sequences(args.content, default_topology=args.topology)}
    if action == "restriction":
        from clonelab.restriction import digest_sequence
        return digest_sequence(args.sequence, enzymes, topology=args.topology)
    if action == "construct":
        from clonelab.hypotheses import construct_hypotheses
        return {"hypotheses": construct_hypotheses(args.vector, args.insert, insertion_start=args.insertion_start, include_tandem=True)}
    if action == "diagnostic":
        from clonelab.diagnostics import optimize_digests
        return optimize_digests(args.hypotheses, enzymes)
    if action == "gel":
        from clonelab.gel import simulate_gel
        return simulate_gel([{"lane_id": f"lane_{i + 1}", "fragment_lengths": lane} for i, lane in enumerate(args.fragments)])
    if action == "interpret":
        from clonelab.interpretation import interpret_bands
        return interpret_bands(args.observed, args.predictions)
    if action == "report":
        from clonelab.reports import export_report
        return export_report(args.project, args.analysis, output_format=args.format)
    if action == "workflow":
        from clonelab.workflow import optimize_construct_design
        return optimize_construct_design(args.vector, args.insert, insertion_start=args.insertion_start, candidate_enzymes=enzymes)
    raise ValueError(f"unknown CloneLab action: {action}")


def _http(action, args, enzymes):
    routes = {
        "restriction": ("/api/v1/clonelab/digests", {"molecule": {"name": "input", "sequence": args.sequence, "topology": args.topology}, "enzymes": enzymes}),
        "construct": ("/api/v1/clonelab/constructs/hypotheses", {"vector": {"name": "vector", "sequence": args.vector, "topology": "circular"}, "insert": {"name": "insert", "sequence": args.insert, "topology": "linear"}, "insertion_start": args.insertion_start, "include_tandem": True}),
        "diagnostic": ("/api/v1/clonelab/assays/optimize", {"hypotheses": args.hypotheses, "candidate_enzymes": enzymes}),
        "gel": ("/api/v1/clonelab/gels/simulate", {"lanes": [{"lane_id": f"lane_{i + 1}", "fragment_lengths": lane} for i, lane in enumerate(args.fragments)]}),
        "interpret": ("/api/v1/clonelab/results/interpret", {"observed_bands_bp": args.observed, "predictions": args.predictions}),
        "report": ("/api/v1/clonelab/reports/export", {"project": args.project, "analysis": args.analysis, "output_format": args.format}),
        "workflow": ("/api/v1/clonelab/workflows/diagnostic-digest", {"vector": {"name": "vector", "sequence": args.vector, "topology": "circular"}, "insert": {"name": "insert", "sequence": args.insert, "topology": "linear"}, "insertion_start": args.insertion_start, "candidate_enzymes": enzymes}),
    }
    if action == "sequence":
        return common.http_post(args.http, "/api/v1/clonelab/sequences/parse", {"content": args.content, "default_topology": args.topology})
    path, payload = routes[action]
    return common.http_post(args.http, path, payload)
