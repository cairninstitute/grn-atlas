#!/usr/bin/env python3
"""Compare RNAi and CRISPR intervention strategies for candidate genes."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-crispr-vs-dsrna-compare")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--intent", default="knockdown", help="Intent: knockdown or knockout")
    args = parser.parse_args()

    payload = {"gene_ids": args.gene_ids.split(","), "intent": args.intent}
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/compare/crispr-vs-dsrna", payload)
    else:
        print("Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
