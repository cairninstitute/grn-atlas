#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Cell-type regulation readiness")
    common.add_common_args(parser)
    parser.add_argument("--species", required=True)
    parser.add_argument("--gene-ids")
    args = parser.parse_args()
    payload = {"species": args.species, "gene_ids": [g.strip() for g in args.gene_ids.split(",")] if args.gene_ids else None}
    if args.http:
        data = common.http_post(args.http, "/api/v1/celltype/regulation", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.celltype_regulation(backend.CelltypeRegulationRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
