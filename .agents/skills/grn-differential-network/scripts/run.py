#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Differential regulatory network between two tissues")
    common.add_common_args(parser)
    parser.add_argument("--species", required=True)
    parser.add_argument("--tissue-a", required=True)
    parser.add_argument("--tissue-b", required=True)
    parser.add_argument("--min-delta", type=float, default=0.3)
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args()
    payload = {
        "species": args.species,
        "tissue_a": args.tissue_a,
        "tissue_b": args.tissue_b,
        "min_delta": args.min_delta,
        "top": args.top,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/network/differential", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.differential_network(backend.DifferentialNetworkRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
