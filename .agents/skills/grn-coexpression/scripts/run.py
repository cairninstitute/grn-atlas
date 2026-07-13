#!/usr/bin/env python3
"""Find genes co-expressed with a given gene."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Find co-expressed genes")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True, help="Gene ID")
    parser.add_argument("--top", type=int, default=20, help="Number of top partners (default 20)")
    parser.add_argument("--min-r", type=float, default=0.5, help="Min absolute correlation (default 0.5)")
    args = parser.parse_args()

    if args.http:
        payload = {
            "gene_id": args.gene_id,
            "top": args.top,
            "min_abs_r": args.min_r,
        }
        data = common.http_post(args.http, "/api/v1/coexpression", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        from main import coexpression, CoexpRequest
        req = CoexpRequest(gene_id=args.gene_id, top=args.top, min_abs_r=args.min_r)
        data = common.run_async(coexpression(req))

    common.output(data)


if __name__ == "__main__":
    main()
