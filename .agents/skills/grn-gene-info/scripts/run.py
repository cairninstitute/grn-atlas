#!/usr/bin/env python3
"""Get detailed information about a specific gene."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Get gene info from GRN Atlas")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", default=None, help="Ensembl gene ID")
    parser.add_argument("--symbol", default=None, help="Gene symbol")
    parser.add_argument("--species", default=None, help="Species (required with --symbol)")
    args = parser.parse_args()

    if not args.gene_id and not args.symbol:
        parser.error("Must provide either --gene-id or --symbol")

    if args.http:
        if args.gene_id:
            data = common.http_get(args.http, f"/api/v1/genes/{args.gene_id}")
        else:
            params = {}
            if args.species:
                params["species"] = args.species
            data = common.http_get(args.http, f"/api/v1/genes/symbol/{args.symbol}", params)
    else:
        db = common.init_db()
        if args.gene_id:
            gene = db.get_gene(args.gene_id)
        else:
            if not args.species:
                parser.error("--species is required when using --symbol")
            gene = db.find_gene_by_symbol_species(args.symbol, args.species)
        if gene is None:
            data = {"error": "Gene not found"}
        else:
            data = gene.model_dump()

    common.output(data)


if __name__ == "__main__":
    main()
