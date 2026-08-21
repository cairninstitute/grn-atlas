#!/usr/bin/env python3
"""Predict regulatory consequences of a gene edit."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-edit-consequence")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True, help="Gene ID")
    parser.add_argument("--edit-type", default="promoter_disruption",
                        help="Edit type: promoter_disruption, coding_disruption, motif_disruption")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--motif-id", default=None, help="Motif ID (for motif_disruption)")
    args = parser.parse_args()

    payload = {"gene_id": args.gene_id, "edit_type": args.edit_type}
    if args.species:
        payload["species"] = args.species
    if args.motif_id:
        payload["motif_id"] = args.motif_id

    if args.http:
        data = common.http_post(args.http, "/api/v1/edit/consequence", payload)
    else:
        print("Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
