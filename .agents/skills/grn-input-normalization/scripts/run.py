#!/usr/bin/env python3
"""Normalize messy user-provided GRN Atlas input before downstream import/analysis."""
import argparse
from collections import Counter
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common
import research_workflows as rw


def _load_content(args):
    if bool(args.content) == bool(args.file):
        raise SystemExit("Provide exactly one of --content or --file")
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return args.content


def _dedupe_summary(rows):
    seen = Counter()
    duplicates = []
    for row in rows:
        token = (row.get("gene_token") or "").strip().lower()
        if not token:
            continue
        seen[token] += 1
    for token, count in seen.items():
        if count > 1:
            duplicates.append({"normalized_token": token, "count": count})
    return duplicates


def _species_distribution(mapped_genes):
    counts = Counter()
    for gene in mapped_genes or []:
        species = gene.get("species")
        if species:
            counts[species] += 1
    return dict(counts)


def _normalize_rows(rows):
    normalized = []
    for row in rows or []:
        gene = row.get("gene") or {}
        normalized.append({
            "row_index": row.get("row_index"),
            "input": row.get("input"),
            "gene_token": row.get("gene_token"),
            "score": row.get("score"),
            "status": row.get("status"),
            "resolved_gene_id": gene.get("gene_id"),
            "resolved_symbol": gene.get("symbol"),
            "resolved_species": gene.get("species"),
            "candidate_count": len(row.get("candidates") or []),
            "extra": row.get("extra"),
        })
    return normalized


def _recommended_next_skill(data):
    summary = data.get("normalization_summary", {})
    mapped = summary.get("mapped_count", len(data.get("mapped_gene_ids", [])))
    ambiguous = summary.get("ambiguous_count", 0)
    unmapped = summary.get("unmapped_count", 0)
    mixed = len((data.get("species_distribution") or {}).keys()) > 1 and not data.get("species_filter")
    if mapped == 0:
        return {
            "skill": "grn_gene_search",
            "reason": "No atlas genes mapped cleanly; resolve identifiers before downstream analysis.",
        }
    if mixed:
        return {
            "skill": "grn_dataset_import",
            "reason": "Mapped rows span multiple species; use an explicit species-filtered import step before analysis.",
        }
    if ambiguous or unmapped:
        return {
            "skill": "grn_dataset_import",
            "reason": "Some rows remain ambiguous or unmapped; review the import report before interpretation.",
        }
    return {
        "skill": "grn_user_gene_set_analysis",
        "reason": "Input is clean enough for first-pass atlas interpretation.",
    }


def _postprocess(raw, source_content):
    species_dist = _species_distribution(raw.get("mapped_genes"))
    duplicates = _dedupe_summary(raw.get("rows") or [])
    mixed_species_detected = len(species_dist) > 1 and not raw.get("species_filter")
    normalized_rows = _normalize_rows(raw.get("rows"))
    result = {
        "input_type": raw.get("dataset_type"),
        "filename": raw.get("filename"),
        "species_filter": raw.get("species_filter"),
        "species_guess": raw.get("species_guess"),
        "species_distribution": species_dist,
        "mixed_species_detected": mixed_species_detected,
        "mapped_gene_ids": raw.get("mapped_gene_ids", []),
        "mapped_rows": [r for r in normalized_rows if r.get("status") == "mapped"],
        "ambiguous_rows": raw.get("ambiguous_rows", []),
        "unmapped_rows": raw.get("unmapped_rows", []),
        "duplicate_inputs": duplicates,
        "normalization_summary": {
            "source_characters": len(source_content or ""),
            "row_count": raw.get("row_count", 0),
            "mapped_count": raw.get("mapped_count", 0),
            "ambiguous_count": raw.get("ambiguous_count", 0),
            "unmapped_count": raw.get("unmapped_count", 0),
            "duplicate_input_count": len(duplicates),
        },
        "match_type_counts": raw.get("match_type_counts", {}),
        "rows": normalized_rows,
        "warnings": raw.get("warnings", []),
    }
    deg_guess = rw.infer_deg_schema(normalized_rows)
    result["detected_columns"] = rw.detect_columns(normalized_rows)
    result["column_role_guess"] = deg_guess["column_roles"]
    result["deg_schema_guess"] = deg_guess["schema_guess"]
    result["ambiguous_identifier_review"] = [
        {
            "input": row.get("input"),
            "candidate_count": len(row.get("candidates", [])),
            "candidate_symbols": [c.get("symbol") for c in row.get("candidates", [])[:5]],
        }
        for row in (raw.get("ambiguous_rows") or [])
    ]
    result["suggested_species_filter"] = max(species_dist, key=species_dist.get) if species_dist else None
    result["recommended_next_skill"] = _recommended_next_skill(result)
    return result


def main():
    parser = argparse.ArgumentParser(description="Normalize messy GRN Atlas input")
    common.add_common_args(parser)
    parser.add_argument("--content", help="Inline pasted content")
    parser.add_argument("--file", help="Path to a local file")
    parser.add_argument("--species", default=None, help="Optional species filter")
    parser.add_argument("--filename", default=None, help="Optional source filename label")
    args = parser.parse_args()

    content = _load_content(args)
    filename = args.filename or (Path(args.file).name if args.file else None)

    if args.http:
        payload = {"content": content, "species": args.species, "filename": filename}
        raw = common.http_post(args.http, "/api/v1/datasets/import", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        raw = common.run_async(
            backend.dataset_import(
                backend.DatasetImportRequest(content=content, species=args.species, filename=filename)
            )
        )

    common.output(_postprocess(raw, content))


if __name__ == "__main__":
    main()
