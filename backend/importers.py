"""User dataset parsing and gene-set import helpers for GRN Atlas."""

from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any


GENE_COLUMNS = {
    "gene", "gene_id", "gene id", "id", "symbol", "gene_symbol", "gene symbol",
    "locus", "ensembl_id", "ensembl id", "agi", "geneid",
}
SCORE_COLUMNS = {
    "score", "rank", "logfc", "log2fc", "lfc", "pvalue", "p_value", "padj", "qvalue",
}


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _normalize_header(name: str) -> str:
    return (name or "").strip().lower().replace("_", " ")


def _guess_table(sample: str) -> tuple[bool, str]:
    lines = [line for line in sample.splitlines() if line.strip()]
    if not lines:
        return False, ""
    first = lines[0]
    for delim in ("\t", ",", ";"):
        if delim not in first:
            continue
        fields = [f.strip() for f in first.split(delim)]
        normalized = {_normalize_header(f) for f in fields}
        if len(fields) > 1 and (normalized & GENE_COLUMNS):
            return True, delim
    return False, ""


def _parse_plain(content: str) -> list[dict[str, Any]]:
    out = []
    for idx, line in enumerate(content.splitlines(), start=1):
        token = line.strip()
        if not token or token.startswith("#"):
            continue
        out.append({
            "row_index": idx,
            "raw_value": token,
            "gene_token": token,
            "score": None,
            "extra": {},
        })
    return out


def _parse_table(content: str, delimiter: str) -> tuple[list[dict[str, Any]], str | None, str | None]:
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if not reader.fieldnames:
        return [], None, None
    by_norm = {_normalize_header(name): name for name in reader.fieldnames}
    gene_col = next((by_norm[k] for k in by_norm if k in GENE_COLUMNS), None)
    score_col = next((by_norm[k] for k in by_norm if k in SCORE_COLUMNS), None)
    rows = []
    for idx, row in enumerate(reader, start=2):
        if not row:
            continue
        gene_token = (row.get(gene_col) or "").strip() if gene_col else ""
        if not gene_token:
            continue
        extra = {k: v for k, v in row.items() if k not in {gene_col, score_col}}
        rows.append({
            "row_index": idx,
            "raw_value": gene_token,
            "gene_token": gene_token,
            "score": (row.get(score_col) or "").strip() if score_col else None,
            "extra": extra,
        })
    return rows, gene_col, score_col


def _candidate_from_gene(gene) -> dict[str, Any]:
    return {
        "gene_id": gene.id,
        "symbol": gene.symbol,
        "species": gene.species,
        "label": getattr(gene, "label", gene.symbol),
        "label_inferred": getattr(gene, "label_inferred", False),
    }


def _map_token(db, token: str, species: str | None = None) -> dict[str, Any]:
    token = (token or "").strip()
    if not token:
        return {"status": "unmapped", "candidates": []}

    exact = db.get_gene(token)
    if exact and (not species or exact.species == species):
        return {"status": "mapped", "gene": exact, "match_type": "exact_id"}

    candidates = []
    if species:
        sym = db.find_gene_by_symbol_species(token, species)
        if sym:
            return {"status": "mapped", "gene": sym, "match_type": "exact_symbol"}
        candidates = db.search_genes(token, limit=10, species=species)
    else:
        candidates = db.search_genes(token, limit=10)

    exact_hits = []
    tok = token.lower()
    for cand in candidates:
        if cand.id.lower() == tok or cand.symbol.lower() == tok:
            exact_hits.append(cand)
            continue
        syns = getattr(cand, "synonyms", None) or []
        if any(s.lower() == tok for s in syns):
            exact_hits.append(cand)

    if len(exact_hits) == 1:
        return {"status": "mapped", "gene": exact_hits[0], "match_type": "exact_alias"}
    if len(exact_hits) > 1:
        return {
            "status": "ambiguous",
            "candidates": [_candidate_from_gene(g) for g in exact_hits[:5]],
            "match_type": "ambiguous_exact",
        }
    if len(candidates) == 1:
        return {"status": "mapped", "gene": candidates[0], "match_type": "search_unique"}
    if len(candidates) > 1:
        return {
            "status": "ambiguous",
            "candidates": [_candidate_from_gene(g) for g in candidates[:5]],
            "match_type": "ambiguous_search",
        }
    return {"status": "unmapped", "candidates": [], "match_type": "not_found"}


def import_gene_dataset(db, content: str, species: str | None = None, filename: str | None = None) -> dict[str, Any]:
    if not (content or "").strip():
        return {
            "dataset_type": "empty",
            "filename": filename,
            "species_filter": species,
            "rows": [],
            "mapped_genes": [],
            "mapped_gene_ids": [],
            "ambiguous_rows": [],
            "unmapped_rows": [],
            "species_guess": species,
            "warnings": ["dataset was empty"],
        }

    is_table, delim = _guess_table(content)
    if is_table:
        rows, gene_column, score_column = _parse_table(content, delim)
        dataset_type = "tabular_gene_set_with_scores" if score_column else "tabular_gene_set"
    else:
        rows = _parse_plain(content)
        gene_column, score_column = None, None
        dataset_type = "plain_gene_list"

    mapped_genes = []
    ambiguous_rows = []
    unmapped_rows = []
    row_results = []
    match_types = Counter()

    for row in rows:
        res = _map_token(db, row["gene_token"], species=species)
        row_out = {
            "row_index": row["row_index"],
            "input": row["raw_value"],
            "gene_token": row["gene_token"],
            "score": row["score"],
            "status": res["status"],
            "extra": row["extra"],
        }
        match_types[res.get("match_type", res["status"])] += 1
        if res["status"] == "mapped":
            gene = res["gene"]
            mapped_genes.append(gene)
            row_out["gene"] = _candidate_from_gene(gene)
        elif res["status"] == "ambiguous":
            row_out["candidates"] = res["candidates"]
            ambiguous_rows.append(row_out)
        else:
            unmapped_rows.append(row_out)
        row_results.append(row_out)

    unique_mapped = []
    seen = set()
    for gene in mapped_genes:
        if gene.id in seen:
            continue
        seen.add(gene.id)
        unique_mapped.append(gene)

    species_counts = Counter(g.species for g in unique_mapped)
    species_guess = species or (species_counts.most_common(1)[0][0] if species_counts else None)
    warnings = []
    if ambiguous_rows:
        warnings.append(f"{len(ambiguous_rows)} row(s) were ambiguous and need manual resolution")
    if unmapped_rows:
        warnings.append(f"{len(unmapped_rows)} row(s) did not map to atlas genes")
    if len(species_counts) > 1 and not species:
        warnings.append("mapped genes span multiple species; downstream analysis will need a species filter")

    return {
        "dataset_type": dataset_type,
        "filename": filename,
        "species_filter": species,
        "species_guess": species_guess,
        "gene_column": gene_column,
        "score_column": score_column,
        "row_count": len(rows),
        "mapped_count": len(unique_mapped),
        "ambiguous_count": len(ambiguous_rows),
        "unmapped_count": len(unmapped_rows),
        "match_type_counts": dict(match_types),
        "mapped_genes": [_candidate_from_gene(g) for g in unique_mapped],
        "mapped_gene_ids": [g.id for g in unique_mapped],
        "ambiguous_rows": ambiguous_rows,
        "unmapped_rows": unmapped_rows,
        "rows": row_results,
        "warnings": warnings,
    }


def normalize_gene_ids(db, gene_ids: list[str], species: str | None = None) -> dict[str, Any]:
    content = "\n".join(_dedupe_preserve([g for g in gene_ids if g]))
    return import_gene_dataset(db, content, species=species)
