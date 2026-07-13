#!/usr/bin/env python3
"""Search for genes by name, symbol, or keyword."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Search genes in GRN Atlas")
    common.add_common_args(parser)
    parser.add_argument("--query", required=True, help="Search term")
    parser.add_argument("--species", default=None, help="Filter by species")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default 20)")
    args = parser.parse_args()

    if args.http:
        params = {"q": args.query, "limit": args.limit}
        if args.species:
            params["species"] = args.species
        data = common.http_get(args.http, "/api/v1/genes/search", params)
    else:
        db = common.init_db()
        genes = db.search_genes(args.query, limit=args.limit, species=args.species)
        data = {"genes": [g.model_dump() for g in genes]}

    common.output(data)


if __name__ == "__main__":
    main()
