#!/usr/bin/env python3
"""Audit evidence support for a gene or regulatory edge."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas evidence audit")
    common.add_common_args(parser)
    parser.add_argument("--scope", required=True, choices=["gene", "edge"])
    parser.add_argument("--gene-id")
    parser.add_argument("--source-id")
    parser.add_argument("--target-id")
    parser.add_argument("--species")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.http:
        params = {"scope": args.scope, "depth": args.depth}
        if args.gene_id:
            params["gene_id"] = args.gene_id
        if args.source_id:
            params["source_id"] = args.source_id
        if args.target_id:
            params["target_id"] = args.target_id
        if args.species:
            params["species"] = args.species
        if args.debug:
            params["debug"] = "true"
        data = common.http_get(args.http, "/api/v1/evidence/audit", params)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(
            backend.evidence_audit(
                scope=args.scope,
                gene_id=args.gene_id,
                source_id=args.source_id,
                target_id=args.target_id,
                species=args.species,
                depth=args.depth,
                debug=args.debug,
            )
        )

    common.output(data)


if __name__ == "__main__":
    main()
