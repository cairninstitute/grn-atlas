#!/usr/bin/env python3
"""Get a comprehensive overview of a species in the atlas: gene counts, interaction counts, TF coverage, data sources, expression panel, and available capabilities."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-organism-overview")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species name")
    args = parser.parse_args()


    if args.http:
        path = "/api/v1/organism/{species}/overview"
        if args.species:
            path = path.replace("{species}", args.species)
        data = common.http_get(args.http, path)
    else:
        print("Use --http mode for this skill")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
