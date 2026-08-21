#!/usr/bin/env python3
"""Compare intervention modes across candidates."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-intervention-strategy-ranker")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--intent", default="knockdown", help="Intent: knockdown or knockout")
    parser.add_argument("--budget", default="moderate", help="Budget: low, moderate, high")
    args = parser.parse_args()

    payload = {"gene_ids": args.gene_ids.split(","), "intent": args.intent, "budget": args.budget}
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/intervention/rank", payload)
    else:
        print("Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
