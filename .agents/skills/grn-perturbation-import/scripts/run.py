#!/usr/bin/env python3
"""Import observed perturbation results (CRISPR screens, knockdown data) for calibrating atlas predictions against experimental evidence."""
import argparse
import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="grn-perturbation-import")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--type", default=None, help="Perturbation type: CRISPR_KO, RNAi, etc.")
    parser.add_argument("--file", default=None, help="Path to observations TSV")
    parser.add_argument("--dataset-label", default=None, help="Stable source dataset/accession label")
    parser.add_argument("--source-url", default=None, help="Source URL retained as provenance")
    args = parser.parse_args()

    payload = {}
    if args.species:
        payload["species"] = args.species
    if args.type:
        payload["perturbation_type"] = args.type
    observations = []
    if args.file:
        with open(args.file, newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                observations.append({
                    "perturbed_gene": row["perturbed_gene"],
                    "affected_gene": row["affected_gene"],
                    "log2fc": float(row.get("log2fc") or 0),
                    "significant": str(row.get("significant", "")).lower() in {"1", "true", "yes"},
                    "dataset_label": row.get("dataset_label") or args.dataset_label,
                    "metadata": {"contrast": row.get("contrast")} if row.get("contrast") else {},
                })
    payload["observations"] = observations
    payload["metadata"] = {
        key: value for key, value in {
            "dataset_label": args.dataset_label,
            "source_url": args.source_url,
            "source_file": Path(args.file).name if args.file else None,
        }.items() if value
    }

    if args.http:
        data = common.http_post(args.http, "/api/v1/perturbation/import", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        request = backend.PerturbationImportRequest(**payload)
        data = asyncio.run(backend.perturbation_import(request))

    common.output(data)


if __name__ == "__main__":
    main()
