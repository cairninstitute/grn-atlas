#!/usr/bin/env python3
"""Find regulatory paths between two genes."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Find regulatory paths between genes")
    common.add_common_args(parser)
    parser.add_argument("--source", required=True, help="Source gene Ensembl ID")
    parser.add_argument("--target", required=True, help="Target gene symbol")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--min-confidence", type=float, default=0.3)
    args = parser.parse_args()

    if args.http:
        payload = {
            "source_gene_id": args.source,
            "target_symbol": args.target,
            "max_depth": args.max_depth,
            "limit": args.limit,
            "min_confidence": args.min_confidence,
        }
        data = common.http_post(args.http, "/api/v1/pathways/pathfinding", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        from main import find_paths, PathFindingRequest
        req = PathFindingRequest(
            source_gene_id=args.source,
            target_symbol=args.target,
            max_depth=args.max_depth,
            limit=args.limit,
            min_confidence=args.min_confidence,
        )
        data = common.run_async(find_paths(req))

    common.output(data)


if __name__ == "__main__":
    main()
