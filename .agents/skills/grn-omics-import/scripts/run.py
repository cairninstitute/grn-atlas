#!/usr/bin/env python3
"""Import a gene expression matrix (bulk, pseudobulk, or scRNA-seq) with optional cluster definitions and DEG contrasts. Creates a dataset for use with cell-type and activity workflows."""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def _load_matrix_file(path_str: str):
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Matrix file not found: {path}")
    text = path.read_text().strip()
    if not text:
        raise ValueError(f"Matrix file is empty: {path}")

    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    if len(rows) < 2:
        raise ValueError("Matrix file must include a header and at least one gene row")

    header = [c.strip() for c in rows[0]]
    if len(header) < 2:
        raise ValueError("Matrix header must include a gene_id column and at least one sample column")
    sample_names = header[1:]

    gene_values = {}
    for idx, row in enumerate(rows[1:], start=2):
        if not row or not any(cell.strip() for cell in row):
            continue
        cells = [c.strip() for c in row]
        if len(cells) != len(header):
            raise ValueError(f"Row {idx} has {len(cells)} columns; expected {len(header)}")
        gene_id = cells[0]
        if not gene_id:
            raise ValueError(f"Row {idx} is missing gene_id")
        try:
            values = [float(v) for v in cells[1:]]
        except ValueError as exc:
            raise ValueError(f"Row {idx} has non-numeric sample values") from exc
        gene_values[gene_id] = values

    if not gene_values:
        raise ValueError("Matrix file did not contain any gene rows")
    return gene_values, sample_names


def _infer_simple_contrast(gene_values, sample_names):
    if len(sample_names) != 2:
        return None
    group_a, group_b = sample_names[0], sample_names[1]
    deg = {}
    for gene_id, values in gene_values.items():
        if len(values) != 2:
            return None
        deg[gene_id] = round(float(values[0]) - float(values[1]), 4)
    return [{"group_a": group_a, "group_b": group_b, "deg": deg}]


def main():
    parser = argparse.ArgumentParser(description="grn-omics-import")
    common.add_common_args(parser)
    parser.add_argument("--name", default=None, help="Dataset name")
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--data-type", default=None, help="Data type: bulk, pseudobulk, scRNA")
    parser.add_argument("--matrix", default=None, help="Path to TSV matrix file")
    args = parser.parse_args()

    payload = {}
    if args.name:
        payload["name"] = args.name
    if args.species:
        payload["species"] = args.species
    if args.data_type:
        payload["data_type"] = args.data_type
    if args.matrix:
        gene_values, sample_names = _load_matrix_file(args.matrix)
        payload["gene_values"] = gene_values
        payload["sample_names"] = sample_names
        inferred_contrasts = _infer_simple_contrast(gene_values, sample_names)
        if inferred_contrasts:
            payload["contrasts"] = inferred_contrasts

    if args.http:
        data = common.http_post(args.http, "/api/v1/import/omics", payload)
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
