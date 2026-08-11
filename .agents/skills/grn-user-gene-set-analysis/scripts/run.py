#!/usr/bin/env python3
"""Run atlas analysis over a user-provided gene set."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def _load_content(args):
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return args.content


def main():
    parser = argparse.ArgumentParser(description="Analyze a user gene set with GRN Atlas")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", help="Comma-separated atlas gene IDs")
    parser.add_argument("--content", help="Inline gene list or CSV/TSV content")
    parser.add_argument("--file", help="Path to a local file to analyze")
    parser.add_argument("--species", default=None, help="Optional species override")
    parser.add_argument("--filename", default=None, help="Optional source filename label")
    parser.add_argument("--intent", default="experiment",
                        choices=["experiment", "network", "rnai", "traits"])
    parser.add_argument("--top-terms", type=int, default=8)
    parser.add_argument("--top-regulators", type=int, default=8)
    parser.add_argument("--top-candidates", type=int, default=5)
    parser.add_argument("--no-subgraph", action="store_true")
    args = parser.parse_args()

    if not args.gene_ids and not args.content and not args.file:
        raise SystemExit("Provide --gene-ids, --content, or --file")

    payload = {
        "gene_ids": [g.strip() for g in args.gene_ids.split(",")] if args.gene_ids else None,
        "content": _load_content(args),
        "species": args.species,
        "filename": args.filename or (Path(args.file).name if args.file else None),
        "intent": args.intent,
        "top_terms": args.top_terms,
        "top_regulators": args.top_regulators,
        "top_candidates": args.top_candidates,
        "include_subgraph": not args.no_subgraph,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/user/gene-set/analyze", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(
            backend.user_gene_set_analyze(backend.UserGeneSetAnalysisRequest(**payload))
        )

    common.output(data)


if __name__ == "__main__":
    main()
