#!/usr/bin/env python3
"""Import chromatin peaks (ATAC-seq, ChIP-seq, DAP-seq) with optional peak-gene linkages. Supports BED-like format with peak type and gene annotations."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-peak-import")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--peaks-file", default=None, help="Path to BED-like peaks file")
    args = parser.parse_args()

    payload = {}
    if args.species:
        payload["species"] = args.species
    if args.peaks_file:
        payload["peaks_file"] = args.peaks_file

    if args.http:
        data = common.http_post(args.http, "/api/v1/chromatin/import-peaks", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.app.router.routes)
        # Direct mode: call endpoint via HTTP for simplicity
        import json
        print(json.dumps(payload, indent=2))
        print("Direct mode not yet supported for this skill. Use --http mode.")
        sys.exit(0)

    common.output(data)


if __name__ == "__main__":
    main()
