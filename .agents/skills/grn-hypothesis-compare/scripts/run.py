#!/usr/bin/env python3
"""Compare competing GRN Atlas hypotheses."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas hypothesis comparison")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs")
    parser.add_argument("--intent", default="experiment")
    parser.add_argument("--species")
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--max-experiments", type=int, default=3)
    args = parser.parse_args()

    gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()]
    payload = {
        "gene_ids": gene_ids,
        "intent": args.intent,
        "species": args.species,
        "max_candidates": args.max_candidates,
        "max_experiments": args.max_experiments,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/research/hypothesis-compare", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.HypothesisCompareRequest(**payload)
        data = common.run_async(backend.hypothesis_compare(req))

    common.output(data)


if __name__ == "__main__":
    main()
