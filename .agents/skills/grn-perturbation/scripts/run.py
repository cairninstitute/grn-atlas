#!/usr/bin/env python3
"""Predict downstream effects of gene perturbation."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="In-silico gene perturbation")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", default=None, help="Single gene ID to perturb")
    parser.add_argument("--gene-ids", default=None,
                        help="Comma-separated gene_id:action pairs for multi-intervention "
                             "(e.g. 'TP53:ko,MYC:oe')")
    parser.add_argument("--action", default="ko", choices=["ko", "oe"],
                        help="Perturbation type for --gene-id (default: ko)")
    parser.add_argument("--depth", type=int, default=4, help="Propagation depth (default 4)")
    parser.add_argument("--min-confidence", type=float, default=0.0,
                        help="Min edge confidence (default 0.0)")
    args = parser.parse_args()

    if not args.gene_id and not args.gene_ids:
        parser.error("provide --gene-id or --gene-ids")

    if args.gene_ids:
        interventions = []
        for pair in args.gene_ids.split(","):
            parts = pair.strip().split(":")
            gid = parts[0]
            act = parts[1] if len(parts) > 1 else "ko"
            interventions.append({"gene_id": gid, "action": act})
    else:
        interventions = [{"gene_id": args.gene_id, "action": args.action}]

    if args.http:
        payload = {
            "interventions": interventions,
            "depth": args.depth,
            "min_confidence": args.min_confidence,
            "include_inferred": True,
        }
        data = common.http_post(args.http, "/api/v1/perturb", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        from main import perturb, PerturbRequest, PerturbInterv
        req = PerturbRequest(
            interventions=[PerturbInterv(**i) for i in interventions],
            depth=args.depth,
            min_confidence=args.min_confidence,
            include_inferred=True,
        )
        data = common.run_async(perturb(req))

    common.output(data)


if __name__ == "__main__":
    main()
