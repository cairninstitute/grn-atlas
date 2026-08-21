#!/usr/bin/env python3
"""View tissue-specific coexpression weights for regulatory edges. Shows which tissues support a TF-target interaction based on expression correlation. Use for tissue-context questions like 'is this edge active in petals?'"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-tissue-coexpression")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", default=None, help="Gene ID to query tissue weights for")
    parser.add_argument("--source-id", default=None, help="Source TF ID for specific edge")
    parser.add_argument("--target-id", default=None, help="Target gene ID for specific edge")
    parser.add_argument("--species", default=None, help="Species to list tissues for")
    args = parser.parse_args()

    payload = {}
    if args.gene_id:
        payload["gene_id"] = args.gene_id
    if args.source_id:
        payload["source_id"] = args.source_id
    if args.target_id:
        payload["target_id"] = args.target_id
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/edge-tissues/{gene_id}".format(**vars(args)), payload)
    else:
        print("Use --http mode for this skill")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
