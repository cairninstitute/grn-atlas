#!/usr/bin/env python3
"""Design or analyze dsRNA sequences for RNAi gene silencing."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Design or analyze dsRNA for RNAi")
    common.add_common_args(parser)
    parser.add_argument("--sequence", default=None, help="dsRNA sequence to analyze")
    parser.add_argument("--target-gene", default=None, help="Target gene ID for design mode")
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--k", type=int, default=21, help="siRNA k-mer length (default 21)")
    args = parser.parse_args()

    if not args.sequence and not args.target_gene:
        parser.error("provide either --sequence or --target-gene (+ --species)")

    payload = {"k": args.k}
    if args.sequence:
        payload["sequence"] = args.sequence
    if args.target_gene:
        payload["target_gene_id"] = args.target_gene
    if args.species:
        payload["species"] = args.species

    if args.http:
        data = common.http_post(args.http, "/api/v1/dsrna", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.DsRnaRequest(**payload)
        data = common.run_async(backend.dsrna_analysis(req))

    common.output(data)


if __name__ == "__main__":
    main()
