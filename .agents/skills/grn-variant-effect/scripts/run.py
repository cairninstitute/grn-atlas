#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Promoter variant effect analysis")
    common.add_common_args(parser)
    parser.add_argument("--gene-id", required=True)
    parser.add_argument("--position", required=True, type=int)
    parser.add_argument("--assembly")
    parser.add_argument("--window-type", default="promoter")
    parser.add_argument("--ref")
    parser.add_argument("--alt")
    args = parser.parse_args()
    payload = {
        "gene_id": args.gene_id,
        "position": args.position,
        "assembly": args.assembly,
        "window_type": args.window_type,
        "ref": args.ref,
        "alt": args.alt,
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/variants/effect", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.variant_effect(backend.VariantEffectRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
