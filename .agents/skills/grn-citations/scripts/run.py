#!/usr/bin/env python3
"""Export BibTeX citations for GRN Atlas data sources."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="GRN Atlas BibTeX citations")
    common.add_common_args(parser)
    args = parser.parse_args()

    if args.http:
        import requests
        resp = requests.get(f"{args.http}/api/v1/citations.bib")
        resp.raise_for_status()
        print(resp.text)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import provenance
        print(provenance.bibtex())


if __name__ == "__main__":
    main()
