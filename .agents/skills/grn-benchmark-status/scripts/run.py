#!/usr/bin/env python3
"""View the living validation dashboard: atlas summary statistics, BEELINE benchmark AUROC/AUPRC, per-species validation reports, and quality assessments."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-benchmark-status")
    common.add_common_args(parser)
    args = parser.parse_args()


    if args.http:
        data = common.http_get(args.http, "/api/v1/benchmark/status")
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        db = common.init_db()
        import main as backend
        data = common.run_async(backend.status())

    common.output(data)


if __name__ == "__main__":
    main()
