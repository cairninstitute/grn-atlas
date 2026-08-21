#!/usr/bin/env python3
"""Scan the transcriptome for CRISPR guide off-targets with configurable mismatch tolerance. Reports gene hits, positions, and mismatch counts."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-crispr-offtargets")
    common.add_common_args(parser)
    parser.add_argument("--guide", default=None, help="20-nt guide sequence")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--max-mismatches", default=None, help="Maximum mismatches (default 3)")
    args = parser.parse_args()

    payload = {}
    if args.guide:
        payload["guide_sequence"] = args.guide
    if args.species:
        payload["species"] = args.species
    if args.max_mismatches:
        payload["max_mismatches"] = int(args.max_mismatches)

    if args.http:
        data = common.http_post(args.http, "/api/v1/crispr/offtargets", payload)
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
