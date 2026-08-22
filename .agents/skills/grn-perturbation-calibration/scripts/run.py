#!/usr/bin/env python3
"""Compare predicted downstream effects with observed perturbation data. Reports concordance rate, direction agreement, and prediction accuracy."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-perturbation-calibration")
    common.add_common_args(parser)
    parser.add_argument("--gene", default=None, help="Perturbed gene ID or symbol")
    parser.add_argument("--species", default=None, help="Species")
    args = parser.parse_args()

    payload = {}
    if args.gene:
        payload["perturbed_gene"] = args.gene
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/perturbation/compare", payload)
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
