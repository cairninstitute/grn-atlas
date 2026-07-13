#!/usr/bin/env python3
"""Detect co-regulated gene modules/communities in a regulatory network."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Network module/community detection")
    common.add_common_args(parser)
    parser.add_argument("--species", required=True, help="Species name")
    parser.add_argument("--algorithm", default="louvain",
                        choices=["leiden", "louvain", "infomap", "label_propagation"],
                        help="Community detection algorithm (default: louvain)")
    parser.add_argument("--gene-id", default=None, help="Find this gene's module")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Min edge confidence")
    parser.add_argument("--no-include-inferred", action="store_true", help="Exclude inferred edges")
    parser.add_argument("--resolution", type=float, default=1.0, help="Resolution for leiden/louvain")
    parser.add_argument("--top-modules", type=int, default=20, help="Max modules to return (default 20)")
    args = parser.parse_args()

    payload = {
        "species": args.species,
        "algorithm": args.algorithm,
        "gene_id": args.gene_id,
        "min_confidence": args.min_confidence,
        "include_inferred": not args.no_include_inferred,
        "resolution": args.resolution,
        "top_modules": args.top_modules,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/network/modules", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.get_modules(backend.ModuleRequest(**payload)))

    common.output(data)


if __name__ == "__main__":
    main()
