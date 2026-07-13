#!/usr/bin/env python3
"""Get the data provenance manifest for the GRN Atlas database."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas data provenance")
    common.add_common_args(parser)
    parser.add_argument("--freshness", action="store_true",
                        help="Show data freshness audit instead of full manifest")
    args = parser.parse_args()

    if args.freshness:
        if args.http:
            data = common.http_get(args.http, "/api/v1/provenance/freshness")
        else:
            sys.path.insert(0, str(common.BACKEND_DIR))
            import provenance
            data = provenance.freshness()
    else:
        if args.http:
            data = common.http_get(args.http, "/api/v1/provenance")
        else:
            sys.path.insert(0, str(common.BACKEND_DIR))
            import provenance
            data = provenance.manifest()

    common.output(data)


if __name__ == "__main__":
    main()
