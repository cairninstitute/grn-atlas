#!/usr/bin/env python3
"""Test which TF regulons are enriched in a gene list using hypergeometric test with BH FDR correction. The standard 'which TFs regulate my DEG list?' analysis (decoupleR/DoRothEA convention)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-regulon-enrichment")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", default=None, help="Comma-separated gene IDs to test")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--min-confidence", default=None, help="Minimum edge confidence (default 0.4)")
    parser.add_argument("--top", default=None, help="Number of top TFs (default 25)")
    args = parser.parse_args()

    payload = {}
    if args.gene_ids:
        payload["gene_ids"] = args.gene_ids.split(",")
    if args.species:
        payload["species"] = args.species
    if args.min_confidence:
        payload["min_confidence"] = args.min_confidence
    if args.top:
        payload["top"] = float(args.top)

    if args.http:
        data = common.http_post(args.http, "/api/v1/regulon-enrichment", payload)
    else:
        print("Use --http mode for this skill")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
