#!/usr/bin/env python3
"""Find cross-species orthologs of a gene and their regulatory networks."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Gene orthology lookup")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True, help="Ensembl gene ID")
    parser.add_argument("--species", default=None,
                        help="Comma-separated target species (default: human,arabidopsis,rice)")
    args = parser.parse_args()

    if args.http:
        params = {}
        if args.species:
            params["species"] = args.species
        data = common.http_get(args.http, f"/api/v1/genes/orthology/{args.gene_id}", params or None)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.get_orthology(args.gene_id, species=args.species))

    common.output(data)


if __name__ == "__main__":
    main()
