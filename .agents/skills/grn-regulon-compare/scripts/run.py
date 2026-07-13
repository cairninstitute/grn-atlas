#!/usr/bin/env python3
"""Compare two TFs' regulons."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Compare two TF regulons")
    common.add_common_args(parser)
    parser.add_argument("--tf-a", required=True, help="First TF gene ID")
    parser.add_argument("--tf-b", required=True, help="Second TF gene ID")
    parser.add_argument("--depth", type=int, default=2, help="Expansion depth (default 2)")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Min edge confidence")
    parser.add_argument("--no-include-inferred", action="store_true", help="Exclude inferred edges")
    args = parser.parse_args()

    payload = {
        "tf_a": args.tf_a,
        "tf_b": args.tf_b,
        "depth": args.depth,
        "min_confidence": args.min_confidence,
        "include_inferred": not args.no_include_inferred,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/regulon/compare", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.regulon_compare(backend.RegulonCompareRequest(**payload)))

    common.output(data)


if __name__ == "__main__":
    main()
