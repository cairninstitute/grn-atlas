#!/usr/bin/env python3
"""Predict upstream regulators for a gene set."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Upstream regulator prediction")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--depth", type=int, default=1, help="Regulon depth (default 1)")
    parser.add_argument("--top", type=int, default=50, help="Max regulators to return")
    parser.add_argument("--min-overlap", type=int, default=2, help="Min overlap count")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Min edge confidence")
    parser.add_argument("--no-include-inferred", action="store_true", help="Exclude inferred edges")
    args = parser.parse_args()

    gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()]

    payload = {
        "gene_ids": gene_ids,
        "species": args.species,
        "depth": args.depth,
        "top": args.top,
        "min_overlap": args.min_overlap,
        "min_confidence": args.min_confidence,
        "include_inferred": not args.no_include_inferred,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/upstream-regulators", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.upstream_regulators(backend.UpstreamRequest(**payload)))

    common.output(data)


if __name__ == "__main__":
    main()
