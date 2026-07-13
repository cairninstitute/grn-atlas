#!/usr/bin/env python3
"""Analyze conservation of regulatory edges between two species."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Cross-species regulatory conservation")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs")
    parser.add_argument("--species-b", required=True, help="Species to compare against")
    args = parser.parse_args()

    gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()]
    payload = {"gene_ids": gene_ids, "species_b": args.species_b}

    if args.http:
        data = common.http_post(args.http, "/api/v1/conservation", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.ConservationRequest(**payload)
        data = common.run_async(backend.conservation(req))

    common.output(data)


if __name__ == "__main__":
    main()
