#!/usr/bin/env python3
"""Extract a TF's regulon filtered by cell-type expression context."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-celltype-regulon")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True, help="TF gene ID")
    parser.add_argument("--dataset-id", default=None, help="Imported dataset ID")
    parser.add_argument("--cluster-id", default=None, help="Cluster/cell-type ID")
    parser.add_argument("--species", default=None, help="Species")
    args = parser.parse_args()

    payload = {"gene_id": args.gene_id}
    if args.dataset_id:
        payload["dataset_id"] = args.dataset_id
    if args.cluster_id:
        payload["cluster_id"] = args.cluster_id
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/celltype/regulon", payload)
    else:
        print("Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
