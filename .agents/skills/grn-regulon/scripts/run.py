#!/usr/bin/env python3
"""Extract the full regulon of a transcription factor."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Extract TF regulon")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True, help="Transcription factor gene ID")
    parser.add_argument("--depth", type=int, default=2, help="Expansion depth (default 2)")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Min edge confidence")
    parser.add_argument("--no-include-inferred", action="store_true", help="Exclude inferred edges")
    args = parser.parse_args()

    payload = {
        "gene_id": args.gene_id,
        "depth": args.depth,
        "min_confidence": args.min_confidence,
        "include_inferred": not args.no_include_inferred,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/regulon", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.get_regulon(backend.RegulonRequest(**payload)))

    common.output(data)


if __name__ == "__main__":
    main()
