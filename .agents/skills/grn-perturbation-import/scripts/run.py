#!/usr/bin/env python3
"""Import observed perturbation results (CRISPR screens, knockdown data) for calibrating atlas predictions against experimental evidence."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-perturbation-import")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--type", default=None, help="Perturbation type: CRISPR_KO, RNAi, etc.")
    parser.add_argument("--file", default=None, help="Path to observations TSV")
    args = parser.parse_args()

    payload = {}
    if args.species:
        payload["species"] = args.species
    if args.type:
        payload["perturbation_type"] = args.type
    if args.file:
        payload["file"] = args.file

    if args.http:
        data = common.http_post(args.http, "/api/v1/perturbation/import", payload)
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
