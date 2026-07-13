#!/usr/bin/env python3
"""Explore the regulatory network neighborhood of a gene."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Get gene regulatory neighborhood")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True, help="Ensembl gene ID")
    parser.add_argument("--direction", default="both", choices=["both", "regulators", "targets"])
    parser.add_argument("--min-confidence", type=float, default=0.3)
    parser.add_argument("--no-include-inferred", action="store_true",
                        help="Exclude inferred edges")
    args = parser.parse_args()

    include_inferred = not args.no_include_inferred

    if args.http:
        payload = {
            "direction": args.direction,
            "min_confidence": args.min_confidence,
            "include_inferred": include_inferred,
        }
        data = common.http_post(args.http, f"/api/v1/pathways/neighborhood/{args.gene_id}", payload)
    else:
        db = common.init_db()
        gene = db.get_gene(args.gene_id)
        if gene is None:
            common.output({"error": f"Gene {args.gene_id} not found"})
            return

        result = {"center": gene.model_dump(), "regulators": [], "targets": []}

        if args.direction in ("both", "regulators"):
            regs = db.get_regulators(args.gene_id, min_confidence=args.min_confidence,
                                     include_inferred=include_inferred)
            result["regulators"] = [r.model_dump() for r in regs]

        if args.direction in ("both", "targets"):
            tgts = db.get_targets(args.gene_id, min_confidence=args.min_confidence,
                                  include_inferred=include_inferred)
            result["targets"] = [t.model_dump() for t in tgts]

        data = result

    common.output(data)


if __name__ == "__main__":
    main()
