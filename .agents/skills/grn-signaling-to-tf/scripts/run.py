#!/usr/bin/env python3
"""Trace a receptor or ligand through the regulatory network to identify downstream TF targets. Reports direct TF targets and secondary cascade TFs (2-hop)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-signaling-to-tf")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--receptor", default=None, help="Receptor gene ID")
    parser.add_argument("--ligand", default=None, help="Ligand gene ID")
    args = parser.parse_args()

    payload = {}
    if args.species:
        payload["species"] = args.species
    if args.receptor:
        payload["receptor_gene"] = args.receptor
    if args.ligand:
        payload["ligand_gene"] = args.ligand

    if args.http:
        data = common.http_post(args.http, "/api/v1/signaling/to-tf", payload)
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
