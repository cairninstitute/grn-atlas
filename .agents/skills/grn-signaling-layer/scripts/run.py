#!/usr/bin/env python3
"""Query the non-transcriptional regulatory layer."""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Query the signalling layer")
    common.add_common_args(parser)
    parser.add_argument("--summary", action="store_true",
                        help="what the layer holds, by species, layer and source")
    parser.add_argument("--gene-id", help="gene to inspect")
    parser.add_argument("--trace", action="store_true",
                        help="walk upstream from --gene-id")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--direction", choices=["both", "upstream", "downstream"],
                        default="both")
    parser.add_argument("--species")
    parser.add_argument("--layers", help="comma-separated regulatory layers")
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    if not args.summary and not args.gene_id:
        parser.error("give --summary or --gene-id")
    layers = [s.strip() for s in args.layers.split(",")] if args.layers else None

    if args.http:
        # There is no server-side endpoint for this layer: main.py does not
        # reference regulatory_layer_edges at all. Say so rather than 404.
        common.output({
            "error": "no HTTP endpoint exists for the signalling layer; "
                     "re-run without --http to query the database directly",
            "status_code": 501,
        })
        return

    sys.path.insert(0, str(common.BACKEND_DIR))
    import signaling_layer

    conn = sqlite3.connect(f"file:{common.DB_PATH}?mode=ro", uri=True)
    try:
        if args.summary:
            data = signaling_layer.summary(conn, species=args.species)
        elif args.trace:
            data = signaling_layer.trace_to_tf(
                conn, args.gene_id, depth=args.depth, species=args.species,
                min_confidence=args.min_confidence)
        else:
            data = signaling_layer.neighborhood(
                conn, args.gene_id, species=args.species, layers=layers,
                min_confidence=args.min_confidence, direction=args.direction,
                limit=args.limit)
    finally:
        conn.close()
    common.output(data)


if __name__ == "__main__":
    main()
