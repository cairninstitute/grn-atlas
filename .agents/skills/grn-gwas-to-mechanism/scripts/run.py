#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GWAS/trait-associated gene to regulatory mechanism")
    common.add_common_args(parser)
    parser.add_argument("--gene", required=True)
    parser.add_argument("--species")
    parser.add_argument("--min-confidence", type=float, default=0.4)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()
    payload = {
        "gene": args.gene,
        "species": args.species,
        "min_confidence": args.min_confidence,
        "top": args.top,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/traits/mechanism", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.gwas_to_mechanism(backend.GwasMechanismRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
