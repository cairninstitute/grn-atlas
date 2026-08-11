#!/usr/bin/env python3
"""Import a user gene list or simple table into atlas-normalized genes."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def _load_content(args):
    if bool(args.content) == bool(args.file):
        raise SystemExit("Provide exactly one of --content or --file")
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return args.content


def main():
    parser = argparse.ArgumentParser(description="Import a user gene dataset into GRN Atlas")
    common.add_common_args(parser)
    parser.add_argument("--content", help="Inline gene list or CSV/TSV content")
    parser.add_argument("--file", help="Path to a local file to import")
    parser.add_argument("--species", default=None, help="Optional species filter")
    parser.add_argument("--filename", default=None, help="Optional source filename label")
    args = parser.parse_args()

    content = _load_content(args)
    filename = args.filename or (Path(args.file).name if args.file else None)

    if args.http:
        payload = {"content": content, "species": args.species, "filename": filename}
        data = common.http_post(args.http, "/api/v1/datasets/import", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(
            backend.dataset_import(
                backend.DatasetImportRequest(content=content, species=args.species, filename=filename)
            )
        )

    common.output(data)


if __name__ == "__main__":
    main()
