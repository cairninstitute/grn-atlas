#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Cross-species dsRNA biosafety / off-target screen")
    common.add_common_args(parser)
    parser.add_argument("--sequence")
    parser.add_argument("--target-gene-id")
    parser.add_argument("--intended-species")
    parser.add_argument("--k", type=int, default=21)
    parser.add_argument("--design-window", type=int, default=250)
    parser.add_argument("--top-hits", type=int, default=10)
    args = parser.parse_args()
    payload = {
        "sequence": args.sequence,
        "target_gene_id": args.target_gene_id,
        "intended_species": args.intended_species,
        "k": args.k,
        "design_window": args.design_window,
        "top_hits": args.top_hits,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/rnai/biosafety-screen", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.rnai_biosafety_screen(backend.BiosafetyScreenRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
