#!/usr/bin/env python3
"""Query GWAS trait associations for a gene or test trait enrichment in a gene list. Connects regulatory network genes to phenotypic outcomes."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-trait-association")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", default=None, help="Gene ID for trait lookup")
    parser.add_argument("--gene-ids", default=None, help="Comma-separated gene IDs for trait enrichment")
    parser.add_argument("--species", default=None, help="Species name")
    args = parser.parse_args()

    payload = {}
    if args.gene_id:
        payload["gene_id"] = args.gene_id
    if args.gene_ids:
        payload["gene_ids"] = args.gene_ids.split(",")
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/trait_enrichment", payload)
    else:
        print("Use --http mode for this skill")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
