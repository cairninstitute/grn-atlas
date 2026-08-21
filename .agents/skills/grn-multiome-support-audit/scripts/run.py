#!/usr/bin/env python3
"""Multi-layer evidence triangulation for a biological claim."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-multiome-support-audit")
    common.add_common_args(parser)
    parser.add_argument("--source-id", required=True, help="Source TF gene ID")
    parser.add_argument("--target-id", required=True, help="Target gene ID")
    parser.add_argument("--species", default=None, help="Species")
    args = parser.parse_args()

    payload = {"source_id": args.source_id, "target_id": args.target_id}
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/multiome/audit", payload)
    else:
        print("Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
