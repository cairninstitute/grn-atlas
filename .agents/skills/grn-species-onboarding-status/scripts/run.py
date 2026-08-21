#!/usr/bin/env python3
"""Get onboarding readiness assessment for a species: gene count, edge count, TF annotation, transcriptome availability, ortholog coverage, and overall readiness score (0-1)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-species-onboarding-status")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species name to assess")
    args = parser.parse_args()


    if args.http:
        path = "/api/v1/species/onboarding/{species}"
        if args.species:
            path = path.replace("{species}", args.species)
        data = common.http_get(args.http, path)
    else:
        print("Use --http mode for this skill")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
