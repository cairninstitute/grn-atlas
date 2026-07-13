#!/usr/bin/env python3
"""Query TF binding motif hits in gene promoters."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Motif/promoter analysis")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", default=None, help="Target gene ID")
    parser.add_argument("--tf-gene-id", default=None, help="TF gene ID")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--max-pvalue", type=float, default=1e-4, help="Max p-value (default 1e-4)")
    parser.add_argument("--min-score", type=float, default=0.0, help="Min score (default 0)")
    parser.add_argument("--include-edge-support", action="store_true", help="Cross-ref with regulatory edges")
    parser.add_argument("--top", type=int, default=100, help="Max results (default 100)")
    args = parser.parse_args()

    if not args.gene_id and not args.tf_gene_id:
        parser.error("provide --gene-id or --tf-gene-id")

    payload = {
        "gene_id": args.gene_id,
        "tf_gene_id": args.tf_gene_id,
        "species": args.species,
        "max_pvalue": args.max_pvalue,
        "min_score": args.min_score,
        "include_edge_support": args.include_edge_support,
        "top": args.top,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/motif/query", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.motif_query(backend.MotifQueryRequest(**payload)))

    common.output(data)


if __name__ == "__main__":
    main()
