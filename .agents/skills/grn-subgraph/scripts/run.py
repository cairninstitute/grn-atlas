#!/usr/bin/env python3
"""Extract the induced regulatory subgraph for a set of genes."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Regulatory subgraph extraction")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs")
    args = parser.parse_args()

    gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()]
    payload = {"gene_ids": gene_ids}

    if args.http:
        data = common.http_post(args.http, "/api/v1/pathways/subgraph", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.SubgraphRequest(**payload)
        data = common.run_async(backend.get_subgraph(req))

    common.output(data)


if __name__ == "__main__":
    main()
