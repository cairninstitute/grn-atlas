#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Promoter edit prioritization")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    payload = {"gene_id": args.gene_id, "top": args.top}
    if args.http:
        data = common.http_post(args.http, "/api/v1/promoter/edit-prioritize", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.promoter_edit_prioritize(backend.PromoterEditPrioritizationRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
