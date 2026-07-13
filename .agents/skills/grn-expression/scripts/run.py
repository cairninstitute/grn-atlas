#!/usr/bin/env python3
"""Get expression profile of a gene across RNA-seq samples."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Get gene expression profile")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True, help="Gene ID")
    args = parser.parse_args()

    if args.http:
        data = common.http_get(args.http, f"/api/v1/expression/{args.gene_id}")
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        from main import gene_expression
        data = common.run_async(gene_expression(args.gene_id))

    common.output(data)


if __name__ == "__main__":
    main()
