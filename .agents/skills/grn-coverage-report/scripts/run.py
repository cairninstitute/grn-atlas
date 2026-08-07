#!/usr/bin/env python3
"""Report species/layer coverage for a requested analysis intent."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas coverage report")
    common.add_common_args(parser)
    parser.add_argument("--species", required=True)
    parser.add_argument("--intent", required=True,
                        choices=["network", "expression", "motif", "perturbation",
                                 "orthology", "traits", "rnai", "experiment"])
    parser.add_argument("--gene-id")
    args = parser.parse_args()

    if args.http:
        params = {"species": args.species, "intent": args.intent}
        if args.gene_id:
            params["gene_id"] = args.gene_id
        data = common.http_get(args.http, "/api/v1/coverage/report", params)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(
            backend.coverage_report(
                species=args.species,
                intent=args.intent,
                gene_id=args.gene_id,
            )
        )

    common.output(data)


if __name__ == "__main__":
    main()
