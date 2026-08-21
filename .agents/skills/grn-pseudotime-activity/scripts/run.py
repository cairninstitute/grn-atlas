#!/usr/bin/env python3
"""Score TF activity along a pseudotime-ordered gene expression gradient. Identifies TFs whose regulon members show coordinated changes."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-pseudotime-activity")
    common.add_common_args(parser)
    parser.add_argument("--dataset-id", default=None, help="Imported dataset ID")
    parser.add_argument("--genes", default=None, help="Comma-separated gene_id:value pairs")
    parser.add_argument("--species", default=None, help="Species")
    args = parser.parse_args()

    payload = {}
    if args.dataset_id:
        payload["dataset_id"] = args.dataset_id
    if args.genes:
        payload["gene_values"] = dict(p.split(":") for p in args.genes.split(","))
        payload["gene_values"] = {k: float(v) for k, v in payload["gene_values"].items()}
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/trajectory/activity", payload)
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
