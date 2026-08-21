#!/usr/bin/env python3
"""Inspect a gene's enhancer-linked regulatory neighborhood."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-enhancer-network")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True, help="Gene ID")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--min-link-score", type=float, default=0.1)
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()

    payload = {"gene_id": args.gene_id, "min_link_score": args.min_link_score, "top": args.top}
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/enhancer/network", payload)
    else:
        print("Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
