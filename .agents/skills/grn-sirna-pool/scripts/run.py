#!/usr/bin/env python3
"""Score all siRNAs in a dsRNA window for efficacy using Reynolds/Ui-Tei heuristic rules. Reports GC content, thermodynamic asymmetry, repeat penalties, and ranked efficacy scores."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-sirna-pool")
    common.add_common_args(parser)
    parser.add_argument("--sequence", default=None, help="dsRNA sequence")
    parser.add_argument("--k", default=None, help="siRNA length (default 21)")
    parser.add_argument("--top", default=None, help="Number of top siRNAs to return (default 10)")
    args = parser.parse_args()

    payload = {}
    if args.sequence:
        payload["sequence"] = args.sequence
    if args.k:
        payload["k"] = int(args.k)
    if args.top:
        payload["top"] = int(args.top)

    if args.http:
        data = common.http_post(args.http, "/api/v1/dsrna/sirna-pool", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.app.router.routes)
        # Direct mode: call endpoint via HTTP for simplicity
        import json
        print(json.dumps(payload, indent=2))
        print("Direct mode not yet supported for this skill. Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
