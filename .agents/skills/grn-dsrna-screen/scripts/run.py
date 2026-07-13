#!/usr/bin/env python3
"""Batch dsRNA designability screen across a gene set or pathway."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Batch dsRNA screen")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", default=None, help="Comma-separated gene IDs")
    parser.add_argument("--pathway-id", default=None, help="Pathway ID to screen")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--k", type=int, default=21, help="siRNA k-mer length (default 21)")
    parser.add_argument("--design-window", type=int, default=250, help="Design window size (default 250)")
    parser.add_argument("--no-predict-effect", action="store_true", help="Skip effect prediction")
    args = parser.parse_args()

    if not args.gene_ids and not args.pathway_id:
        parser.error("provide --gene-ids or --pathway-id")

    gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()] if args.gene_ids else None

    payload = {
        "gene_ids": gene_ids,
        "pathway_id": args.pathway_id,
        "species": args.species,
        "k": args.k,
        "design_window": args.design_window,
        "predict_effect": not args.no_predict_effect,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/dsrna/screen", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.DsRnaScreenRequest(
            gene_ids=gene_ids,
            pathway_id=args.pathway_id,
            species=args.species,
            k=args.k,
            design_window=args.design_window,
            predict_effect=not args.no_predict_effect,
        )
        data = common.run_async(backend.dsrna_screen(req))

    common.output(data)


if __name__ == "__main__":
    main()
