#!/usr/bin/env python3
"""Identify TF drivers of a cell-state transition."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-transition-drivers")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", default=None, help="Comma-separated transition DEG gene IDs")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--branch-a", default=None, help="Branch A label")
    parser.add_argument("--branch-b", default=None, help="Branch B label")
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    payload = {"top": args.top}
    if args.gene_ids:
        payload["gene_ids"] = args.gene_ids.split(",")
    if args.species:
        payload["species"] = args.species
    if args.branch_a:
        payload["branch_a"] = args.branch_a
    if args.branch_b:
        payload["branch_b"] = args.branch_b

    if args.http:
        data = common.http_post(args.http, "/api/v1/transition/drivers", payload)
    else:
        print("Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
