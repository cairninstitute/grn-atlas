#!/usr/bin/env python3
"""Score how literature terms map to atlas-grounded candidates."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-literature-grounding")
    common.add_common_args(parser)
    parser.add_argument("--terms", required=True, help="Comma-separated literature terms")
    parser.add_argument("--species", default=None, help="Species filter")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    payload = {"terms": args.terms.split(","), "top": args.top}
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/literature/grounding", payload)
    else:
        print("Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
