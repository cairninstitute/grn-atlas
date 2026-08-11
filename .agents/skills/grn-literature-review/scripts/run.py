#!/usr/bin/env python3
"""External literature review for GRN Atlas questions."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas literature review")
    common.add_common_args(parser)
    parser.add_argument("--scope", required=True, choices=["gene", "edge", "pathway", "phenotype"])
    parser.add_argument("--gene-id")
    parser.add_argument("--source-id")
    parser.add_argument("--target-id")
    parser.add_argument("--query")
    parser.add_argument("--species")
    parser.add_argument("--years-back", type=int, default=5)
    parser.add_argument("--max-results", type=int, default=10)
    args = parser.parse_args()

    params = {
        "scope": args.scope,
        "gene_id": args.gene_id,
        "source_id": args.source_id,
        "target_id": args.target_id,
        "query": args.query,
        "species": args.species,
        "years_back": args.years_back,
        "max_results": args.max_results,
    }
    params = {k: v for k, v in params.items() if v is not None}

    if args.http:
        data = common.http_get(args.http, "/api/v1/literature/review", params)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.literature_review(**params))

    common.output(data)


if __name__ == "__main__":
    main()
