#!/usr/bin/env python3
"""Test which pathways are overrepresented in a gene list using hypergeometric test. Complements GO enrichment (grn-enrichment) with pathway-level analysis."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-pathway-enrichment")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", default=None, help="Comma-separated gene IDs")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--top", default=None, help="Number of top pathways (default 20)")
    args = parser.parse_args()

    payload = {}
    if args.gene_ids:
        payload["gene_ids"] = args.gene_ids.split(",")
    if args.species:
        payload["species"] = args.species
    if args.top:
        payload["top"] = float(args.top)

    if args.http:
        data = common.http_post(args.http, "/api/v1/pathway_enrichment", payload)
    else:
        print("Use --http mode for this skill")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
