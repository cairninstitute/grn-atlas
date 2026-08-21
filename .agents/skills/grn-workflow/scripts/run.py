#!/usr/bin/env python3
"""Run a packaged end-to-end research workflow. Available: deg-to-regulators (DEG list → upstream TFs), target-to-perturbation (gene → RNAi/CRISPR strategy), import-to-activity (dataset → TF scoring)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-workflow")
    common.add_common_args(parser)
    parser.add_argument("--workflow", default=None, help="Workflow type: deg-to-regulators, target-to-perturbation, import-to-activity")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--gene-ids", default=None, help="Comma-separated gene IDs")
    parser.add_argument("--dataset-id", default=None, help="Imported dataset ID")
    args = parser.parse_args()

    payload = {}
    if args.workflow:
        payload["workflow_type"] = args.workflow
    if args.species:
        payload["species"] = args.species
    if args.gene_ids:
        payload["gene_ids"] = args.gene_ids.split(",")
    if args.dataset_id:
        payload["dataset_id"] = args.dataset_id

    if args.http:
        data = common.http_post(args.http, "/api/v1/workflows/run", payload)
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
