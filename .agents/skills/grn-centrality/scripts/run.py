#!/usr/bin/env python3
"""Compute degree centrality metrics for genes in a network."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Network centrality analysis")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--gene-ids", default=None, help="Comma-separated gene IDs")
    parser.add_argument("--metric", default="degree",
                        choices=["degree", "in_degree", "out_degree", "betweenness", "closeness", "eigenvector"],
                        help="Centrality metric (default: degree)")
    parser.add_argument("--top", type=int, default=50, help="Max results (default 50)")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Min edge confidence")
    parser.add_argument("--no-include-inferred", action="store_true", help="Exclude inferred edges")
    args = parser.parse_args()

    if not args.species and not args.gene_ids:
        parser.error("provide --species or --gene-ids")

    gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()] if args.gene_ids else None

    payload = {
        "species": args.species,
        "gene_ids": gene_ids,
        "metric": args.metric,
        "top": args.top,
        "min_confidence": args.min_confidence,
        "include_inferred": not args.no_include_inferred,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/network/centrality", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.get_centrality(backend.CentralityRequest(**payload)))

    common.output(data)


if __name__ == "__main__":
    main()
