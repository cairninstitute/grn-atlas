#!/usr/bin/env python3
"""Compare TF regulatory activity between two groups of conditions/tissues."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Differential regulation analysis")
    common.add_common_args(parser)
    parser.add_argument("--species", required=True, help="Species name")
    parser.add_argument("--tf-gene-id", default=None, help="Specific TF to analyze")
    parser.add_argument("--group-a", required=True, help="Comma-separated tissue names for condition A")
    parser.add_argument("--group-b", required=True, help="Comma-separated tissue names for condition B")
    parser.add_argument("--min-fold-change", type=float, default=1.0, help="Min |log2FC| (default 1.0)")
    parser.add_argument("--top", type=int, default=50, help="Max TFs to return (default 50)")
    args = parser.parse_args()

    group_a = [t.strip() for t in args.group_a.split(",") if t.strip()]
    group_b = [t.strip() for t in args.group_b.split(",") if t.strip()]

    payload = {
        "species": args.species,
        "tf_gene_id": args.tf_gene_id,
        "group_a": group_a,
        "group_b": group_b,
        "min_fold_change": args.min_fold_change,
        "top": args.top,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/differential-regulation", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.differential_regulation(backend.DiffRegulationRequest(**payload)))

    common.output(data)


if __name__ == "__main__":
    main()
