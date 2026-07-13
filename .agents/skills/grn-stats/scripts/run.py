#!/usr/bin/env python3
"""Get atlas-wide or per-species statistics."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas statistics")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species for per-species stats")
    args = parser.parse_args()

    if args.http:
        if args.species:
            data = common.http_get(args.http, f"/api/v1/stats/species/{args.species}")
        else:
            data = common.http_get(args.http, "/api/v1/stats")
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        if args.species:
            data = common.run_async(backend.get_species_stats(args.species))
        else:
            data = common.run_async(backend.get_stats())

    common.output(data)


if __name__ == "__main__":
    main()
