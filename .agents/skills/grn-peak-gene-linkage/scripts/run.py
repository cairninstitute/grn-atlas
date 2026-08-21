#!/usr/bin/env python3
"""Query which genes a genomic region or peak likely regulates."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-peak-gene-linkage")
    common.add_common_args(parser)
    parser.add_argument("--peak-id", default=None, help="Peak ID")
    parser.add_argument("--region", default=None, help="Genomic region chr:start-end")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    payload = {"top": args.top}
    if args.peak_id:
        payload["peak_id"] = args.peak_id
    if args.region:
        payload["region"] = args.region
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/peak-gene/linkage", payload)
    else:
        print("Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
