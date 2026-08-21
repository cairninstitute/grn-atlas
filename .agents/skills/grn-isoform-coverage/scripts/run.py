#!/usr/bin/env python3
"""Check which transcript isoforms of a gene are hit by a dsRNA and how many siRNA sites each isoform has. Use for isoform-aware RNAi design."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-isoform-coverage")
    common.add_common_args(parser)
    parser.add_argument("--target-gene", default=None, help="Target gene ID")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--sequence", default=None, help="Optional dsRNA sequence")
    args = parser.parse_args()

    payload = {}
    if args.target_gene:
        payload["target_gene_id"] = args.target_gene
    if args.species:
        payload["species"] = args.species
    if args.sequence:
        payload["sequence"] = args.sequence

    if args.http:
        data = common.http_post(args.http, "/api/v1/dsrna/isoform-coverage", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.app.router.routes)
        # Direct mode: call endpoint via HTTP for simplicity
        import json
        print(json.dumps(payload, indent=2))
        print("Direct mode not yet supported for this skill. Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
