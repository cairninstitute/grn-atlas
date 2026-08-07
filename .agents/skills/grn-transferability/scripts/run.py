#!/usr/bin/env python3
"""Assess GRN Atlas cross-species transferability."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas transferability assessment")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True)
    parser.add_argument("--target-species", required=True)
    parser.add_argument("--intent", default="experiment")
    args = parser.parse_args()

    payload = {
        "gene_id": args.gene_id,
        "target_species": args.target_species,
        "intent": args.intent,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/research/transferability", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.TransferabilityRequest(**payload)
        data = common.run_async(backend.transferability_assessment(req))

    common.output(data)


if __name__ == "__main__":
    main()
