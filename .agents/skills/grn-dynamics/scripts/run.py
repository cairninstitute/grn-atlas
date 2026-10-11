#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def _parse_perturb(s):
    out = {}
    for item in (s or "").split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            g, v = item.split("=", 1)
        elif ":" in item:
            g, v = item.split(":", 1)
        else:
            continue
        v = v.strip().lower()
        out[g.strip()] = 1 if v in ("1", "on", "oe", "overexpress", "true") else 0
    return out


def main():
    parser = argparse.ArgumentParser(description="Boolean attractor dynamics on a signed regulatory module")
    common.add_common_args(parser)
    parser.add_argument("--genes", required=True, help="comma-separated gene ids/symbols (>=2)")
    parser.add_argument("--species")
    parser.add_argument("--perturb", help="clamped states, e.g. 'TF1=0,TF2=1' (0=knockout, 1=overexpress)")
    parser.add_argument("--initial", choices=["on", "off"], default="on")
    parser.add_argument("--max-steps", type=int, default=50)
    args = parser.parse_args()
    payload = {
        "genes": [g.strip() for g in args.genes.split(",") if g.strip()],
        "species": args.species,
        "perturb": _parse_perturb(args.perturb),
        "initial": args.initial,
        "max_steps": args.max_steps,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/network/dynamics", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.network_dynamics(backend.NetworkDynamicsRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
