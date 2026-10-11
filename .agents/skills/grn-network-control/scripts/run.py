#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Minimal TF driver set to steer a gene program")
    common.add_common_args(parser)
    parser.add_argument("--target-genes", required=True,
                        help="comma-separated atlas gene ids/symbols")
    parser.add_argument("--species")
    parser.add_argument("--desired-direction", choices=["up", "down"])
    parser.add_argument("--max-drivers", type=int, default=10)
    parser.add_argument("--min-confidence", type=float, default=0.4)
    args = parser.parse_args()
    payload = {
        "target_genes": [g.strip() for g in args.target_genes.split(",") if g.strip()],
        "species": args.species,
        "desired_direction": args.desired_direction,
        "max_drivers": args.max_drivers,
        "min_confidence": args.min_confidence,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/network/control", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.network_control(backend.NetworkControlRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
