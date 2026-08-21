#!/usr/bin/env python3
"""Import a gene expression matrix (bulk, pseudobulk, or scRNA-seq) with optional cluster definitions and DEG contrasts. Creates a dataset for use with cell-type and activity workflows."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-omics-import")
    common.add_common_args(parser)
    parser.add_argument("--name", default=None, help="Dataset name")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--data-type", default=None, help="Data type: bulk, pseudobulk, scRNA")
    parser.add_argument("--matrix", default=None, help="Path to TSV matrix file")
    args = parser.parse_args()

    payload = {}
    if args.name:
        payload["name"] = args.name
    if args.species:
        payload["species"] = args.species
    if args.data_type:
        payload["data_type"] = args.data_type
    if args.matrix:
        payload["matrix"] = args.matrix

    if args.http:
        data = common.http_post(args.http, "/api/v1/import/omics", payload)
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
