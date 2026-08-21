#!/usr/bin/env python3
"""Compare CRISPR editing strategies (knockout, CRISPRi, CRISPRa) for a target gene. Assesses suitability based on gene type, regulon size, and reversibility."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-crispr-compare")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", default=None, help="Target gene ID or symbol")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--modes", default=None, help="Comma-separated modes: knockout,CRISPRi,CRISPRa")
    args = parser.parse_args()

    payload = {}
    if args.gene_id:
        payload["gene_id"] = args.gene_id
    if args.species:
        payload["species"] = args.species
    if args.modes:
        payload["modes"] = args.modes.split(",")

    if args.http:
        data = common.http_post(args.http, "/api/v1/crispr/compare", payload)
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
