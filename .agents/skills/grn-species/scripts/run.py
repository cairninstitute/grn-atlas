#!/usr/bin/env python3
"""List all species in the GRN Atlas with their available capabilities."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas species listing")
    common.add_common_args(parser)
    args = parser.parse_args()

    if args.http:
        data = common.http_get(args.http, "/api/v1/species")
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.species_capabilities())

    common.output(data)


if __name__ == "__main__":
    main()
