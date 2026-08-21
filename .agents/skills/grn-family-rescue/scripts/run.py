#!/usr/bin/env python3
"""Rescue regulatory edges for a gene with sparse direct data by aggregating evidence from orthologs across species. Novel targets get reduced confidence (ortholog × edge × 0.7)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-family-rescue")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", default=None, help="Gene ID or symbol")
    args = parser.parse_args()

    payload = {}
    if args.gene_id:
        payload["gene_id"] = args.gene_id

    if args.http:
        data = common.http_post(args.http, "/api/v1/family-rescue", payload)
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
