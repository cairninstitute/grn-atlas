#!/usr/bin/env python3
"""Gene-level differential expression for atlas groups or imported DEG tables."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def _load_content(args):
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return args.content


def main():
    parser = argparse.ArgumentParser(description="Differential expression analysis")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species name")
    parser.add_argument("--group-a", default=None, help="Comma-separated tissues for group A")
    parser.add_argument("--group-b", default=None, help="Comma-separated tissues for group B")
    parser.add_argument("--content", help="Inline precomputed DEG table content")
    parser.add_argument("--file", help="Path to a local DEG table")
    parser.add_argument("--filename", default=None, help="Optional source filename label")
    parser.add_argument("--top", type=int, default=50, help="Max rows to return")
    parser.add_argument("--min-abs-log2fc", type=float, default=0.0, help="Atlas-mode fold-change cutoff")
    args = parser.parse_args()

    if not args.content and not args.file and not (args.species and args.group_a and args.group_b):
        raise SystemExit("Provide atlas groups or an imported DEG table")

    payload = {
        "species": args.species,
        "group_a": [t.strip() for t in args.group_a.split(",")] if args.group_a else [],
        "group_b": [t.strip() for t in args.group_b.split(",")] if args.group_b else [],
        "content": _load_content(args),
        "filename": args.filename or (Path(args.file).name if args.file else None),
        "top": args.top,
        "min_abs_log2fc": args.min_abs_log2fc,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/expression/differential", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(
            backend.differential_expression(backend.DifferentialExpressionRequest(**payload))
        )

    common.output(data)


if __name__ == "__main__":
    main()
