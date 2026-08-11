#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Combinatorial perturbation ranking")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True)
    parser.add_argument("--action", default="ko")
    parser.add_argument("--combo-size", type=int, default=2)
    parser.add_argument("--species")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    payload = {
        "gene_ids": [g.strip() for g in args.gene_ids.split(",") if g.strip()],
        "action": args.action,
        "combo_size": args.combo_size,
        "species": args.species,
        "top": args.top,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/perturb/combinatorial", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.combinatorial_perturbation(backend.CombinatorialPerturbationRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
