#!/usr/bin/env python3
"""Predict regulatory cascade effects from upstream interventions on a target gene."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Predict regulatory cascade")
    common.add_common_args(parser)
    parser.add_argument("--target-gene", required=True, help="Target gene ID")
    parser.add_argument("--interventions", required=True,
                        help="Comma-separated tf_id:direction:magnitude triples "
                             "(e.g. 'SIRT1:up:1.5,MDM2:down:0.5')")
    parser.add_argument("--depth", type=int, default=3, help="Cascade depth (default 3)")
    args = parser.parse_args()

    interventions = []
    for triple in args.interventions.split(","):
        parts = triple.strip().split(":")
        if len(parts) < 2:
            parser.error(f"invalid intervention '{triple}': need tf_id:direction[:magnitude]")
        interventions.append({
            "tf_id": parts[0],
            "direction": parts[1],
            "magnitude": float(parts[2]) if len(parts) > 2 else 1.0,
        })

    payload = {
        "target_gene_id": args.target_gene,
        "interventions": interventions,
        "depth": args.depth,
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/pathway/predict-cascade", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        req = backend.CascadeRequest(
            target_gene_id=args.target_gene,
            interventions=[backend.Intervention(**i) for i in interventions],
            depth=args.depth,
        )
        data = common.run_async(backend.predict_cascade(req))

    common.output(data)


if __name__ == "__main__":
    main()
