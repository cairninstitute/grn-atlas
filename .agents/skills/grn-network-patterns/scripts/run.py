#!/usr/bin/env python3
"""Detect structural network motifs (FFL, autoregulation, bi-fan)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Network pattern detection")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", default=None, help="Comma-separated gene IDs")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--types", default="ffl,autoregulation,bifan",
                        help="Comma-separated pattern types (default: ffl,autoregulation,bifan)")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Min edge confidence")
    parser.add_argument("--limit", type=int, default=100, help="Max patterns (default 100)")
    args = parser.parse_args()

    if not args.gene_ids and not args.species:
        parser.error("provide --gene-ids or --species")

    gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()] if args.gene_ids else None
    pattern_types = [t.strip() for t in args.types.split(",")]

    payload = {
        "gene_ids": gene_ids,
        "species": args.species,
        "pattern_types": pattern_types,
        "min_confidence": args.min_confidence,
        "limit": args.limit,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/network/patterns", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.network_patterns(backend.NetworkPatternRequest(**payload)))

    common.output(data)


if __name__ == "__main__":
    main()
