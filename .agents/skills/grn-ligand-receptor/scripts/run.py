#!/usr/bin/env python3
"""Find potential ligand-receptor signaling pairs from the regulatory network — non-TF genes that regulate TFs, suggesting intercellular signaling relationships."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-ligand-receptor")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--gene-ids", default=None, help="Optional comma-separated gene IDs to filter")
    args = parser.parse_args()

    payload = {}
    if args.species:
        payload["species"] = args.species
    if args.gene_ids:
        payload["gene_ids"] = args.gene_ids.split(",")

    if args.http:
        data = common.http_post(args.http, "/api/v1/signaling/ligand-receptor", payload)
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
