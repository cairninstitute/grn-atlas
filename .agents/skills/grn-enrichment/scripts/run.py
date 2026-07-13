#!/usr/bin/env python3
"""Run overrepresentation analysis on a set of genes."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common

ENDPOINT_MAP = {
    "go": "/api/v1/enrichment",
    "pathway": "/api/v1/pathway_enrichment",
    "trait": "/api/v1/trait_enrichment",
    "motif": "/api/v1/motif_enrichment",
}

FUNC_MAP = {
    "go": "enrichment",
    "pathway": "pathway_enrichment",
    "trait": "trait_enrichment",
    "motif": "motif_enrichment",
}


def main():
    parser = argparse.ArgumentParser(description="Gene set enrichment analysis")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", default=None, help="Comma-separated Ensembl gene IDs")
    parser.add_argument("--gene-id", default=None,
                        help="Single gene ID for trait lookup (returns all trait associations)")
    parser.add_argument("--type", required=True, choices=["go", "pathway", "trait", "motif"],
                        help="Enrichment type")
    parser.add_argument("--species", default=None, help="Species filter")
    args = parser.parse_args()

    if args.gene_id and args.type == "trait":
        if args.http:
            data = common.http_get(args.http, f"/api/v1/traits/{args.gene_id}")
        else:
            sys.path.insert(0, str(common.BACKEND_DIR))
            import main as backend
            data = common.run_async(backend.gene_traits(args.gene_id))
        common.output(data)
        return

    if not args.gene_ids:
        parser.error("--gene-ids is required (or --gene-id with --type trait)")

    gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()]

    if args.http:
        payload = {"gene_ids": gene_ids}
        if args.species:
            payload["species"] = args.species
        data = common.http_post(args.http, ENDPOINT_MAP[args.type], payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        func = getattr(backend, FUNC_MAP[args.type])
        req = backend.EnrichmentRequest(gene_ids=gene_ids, species=args.species)
        data = common.run_async(func(req))

    common.output(data)


if __name__ == "__main__":
    main()
