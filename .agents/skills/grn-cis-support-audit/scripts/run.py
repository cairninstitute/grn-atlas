#!/usr/bin/env python3
"""Audit cis-regulatory support for a TF→target edge across multiple evidence layers."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-cis-support-audit")
    common.add_common_args(parser)
    parser.add_argument("--source-id", required=True, help="TF gene ID")
    parser.add_argument("--target-id", required=True, help="Target gene ID")
    parser.add_argument("--species", default=None, help="Species")
    args = parser.parse_args()

    payload = {"source_id": args.source_id, "target_id": args.target_id}
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/cis-support/audit", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        from unittest.mock import MagicMock
        req = MagicMock()
        req.source_id = args.source_id
        req.target_id = args.target_id
        req.species = args.species
        data = common.run_async(backend.cis_support_audit(req))

    common.output(data)


if __name__ == "__main__":
    main()
