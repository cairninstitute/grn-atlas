#!/usr/bin/env python3
"""View chromatin accessibility peaks, enhancer-gene links, motif hits in peaks, and cis-regulatory support for a gene's regulatory edges."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-chromatin-support")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", default=None, help="Gene ID to query")
    args = parser.parse_args()


    if args.http:
        data = common.http_get(args.http, f"/api/v1/chromatin/gene/{args.gene_id}")
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        db = common.init_db()
        import main as backend
        data = common.run_async(backend.{gene_id}())

    common.output(data)


if __name__ == "__main__":
    main()
