#!/usr/bin/env python3
"""Find upstream TF regulators for a gene set, constrained to TFs that are expressed in a specific cell type or cluster from an imported dataset."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-celltype-upstream")
    common.add_common_args(parser)
    parser.add_argument("--dataset-id", default=None, help="Imported dataset ID")
    parser.add_argument("--cluster-id", default=None, help="Cluster ID")
    parser.add_argument("--gene-ids", default=None, help="Comma-separated gene IDs")
    parser.add_argument("--species", default=None, help="Species")
    args = parser.parse_args()

    payload = {}
    if args.dataset_id:
        payload["dataset_id"] = args.dataset_id
    if args.cluster_id:
        payload["cluster_id"] = args.cluster_id
    if args.gene_ids:
        payload["gene_ids"] = args.gene_ids.split(",")
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/celltype/upstream", payload)
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
