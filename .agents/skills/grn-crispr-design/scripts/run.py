#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="CRISPR guide design")
    common.add_common_args(parser)
    parser.add_argument("--sequence")
    parser.add_argument("--gene-id")
    parser.add_argument("--pam", default="NGG")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    payload = {"sequence": args.sequence, "gene_id": args.gene_id, "pam": args.pam, "top": args.top}
    if args.http:
        data = common.http_post(args.http, "/api/v1/crispr/design", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.crispr_design(backend.CrisprDesignRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
