#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Primer design")
    common.add_common_args(parser)
    parser.add_argument("--sequence")
    parser.add_argument("--gene-id")
    parser.add_argument("--product-min", type=int, default=80)
    parser.add_argument("--product-max", type=int, default=250)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    payload = {
        "sequence": args.sequence,
        "gene_id": args.gene_id,
        "product_min": args.product_min,
        "product_max": args.product_max,
        "top": args.top,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/primers/design", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.primer_design(backend.PrimerDesignRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
