#!/usr/bin/env python3
"""Export regulatory edges with genomic coordinates and promoter windows."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Export regulatory edges")
    common.add_common_args(parser)
    parser.add_argument("--gene-ids", required=True, help="Comma-separated gene IDs")
    parser.add_argument("--format", default="json", choices=["json", "tsv"],
                        help="Output format (default json)")
    args = parser.parse_args()

    gene_ids = [g.strip() for g in args.gene_ids.split(",") if g.strip()]
    payload = {"gene_ids": gene_ids, "format": args.format}

    if args.http:
        if args.format == "tsv":
            import json
            import urllib.request
            req = urllib.request.Request(
                f"{args.http}/api/v1/export/edges",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Accept": "text/plain"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                print(resp.read().decode("utf-8"))
            return
        data = common.http_post(args.http, "/api/v1/export/edges", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.ExportRequest(gene_ids=gene_ids, format=args.format)
        result = common.run_async(backend.export_edges(req))
        if hasattr(result, "body"):
            # TSV returns a PlainTextResponse; extract the text
            print(result.body.decode())
            return
        data = result

    common.output(data)


if __name__ == "__main__":
    main()
