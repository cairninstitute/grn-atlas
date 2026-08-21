#!/usr/bin/env python3
"""Query genome coordinates, chromosomal positions, and cross-species ortholog mappings. Supports genome-aware analyses and coordinate-based lookups."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-genome-browser")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--gene-id", default=None, help="Gene ID for ortholog lookup")
    args = parser.parse_args()


    if args.http:
        path = "/api/v1/genome/{species}"
        if args.species:
            path = path.replace("{species}", args.species)
        data = common.http_get(args.http, path)
    else:
        print("Use --http mode for this skill")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
