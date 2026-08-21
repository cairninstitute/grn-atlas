#!/usr/bin/env python3
"""Query TF binding motif hits in gene promoter regions using JASPAR 2024 position weight matrices. Returns motif positions, scores, and strand information."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-motif-query")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", default=None, help="Gene ID to query promoter motifs for")
    parser.add_argument("--tf-id", default=None, help="Filter to a specific TF motif")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--threshold", default=None, help="Score threshold (default 0.8)")
    args = parser.parse_args()

    payload = {}
    if args.gene_id:
        payload["gene_id"] = args.gene_id
    if args.tf_id:
        payload["tf_id"] = args.tf_id
    if args.species:
        payload["species"] = args.species
    if args.threshold:
        payload["threshold"] = float(args.threshold)

    if args.http:
        data = common.http_post(args.http, "/api/v1/motif/query", payload)
    else:
        print("Use --http mode for this skill")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
