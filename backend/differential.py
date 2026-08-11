"""Gene-level differential-expression helpers for GRN Atlas."""

from __future__ import annotations

import csv
import io
import math
from typing import Any

import expression
import importers


LOGFC_NAMES = {"logfc", "log2fc", "lfc"}
PVAL_NAMES = {"pvalue", "p_value", "pval"}
QVAL_NAMES = {"padj", "qvalue", "q_value", "fdr"}


def _normalize_header(name: str) -> str:
    return (name or "").strip().lower().replace("_", " ")


def _guess_delim(content: str) -> str:
    first = next((line for line in content.splitlines() if line.strip()), "")
    for delim in ("\t", ",", ";"):
        if delim in first:
            return delim
    return ","


def _find_column(fieldnames: list[str], names: set[str]) -> str | None:
    for name in fieldnames:
        if _normalize_header(name) in names:
            return name
    return None


def analyze_imported_deg_table(db, content: str, species: str | None = None,
                               filename: str | None = None, top: int = 50) -> dict[str, Any]:
    delim = _guess_delim(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delim)
    if not reader.fieldnames:
        return {"mode": "imported_table", "filename": filename, "results": [], "warnings": ["table had no header"]}

    fieldnames = reader.fieldnames
    gene_col = _find_column(fieldnames, importers.GENE_COLUMNS)
    logfc_col = _find_column(fieldnames, LOGFC_NAMES)
    pval_col = _find_column(fieldnames, PVAL_NAMES)
    qval_col = _find_column(fieldnames, QVAL_NAMES)
    if not gene_col or not logfc_col:
        return {
            "mode": "imported_table",
            "filename": filename,
            "results": [],
            "warnings": ["table must include a gene column and a logFC/log2FC/LFC column"],
        }

    mapped = []
    warnings = []
    ambiguous = 0
    unmapped = 0
    species_counts: dict[str, int] = {}

    for idx, row in enumerate(reader, start=2):
        token = (row.get(gene_col) or "").strip()
        raw_fc = (row.get(logfc_col) or "").strip()
        if not token or not raw_fc:
            continue
        try:
            log2fc = float(raw_fc)
        except ValueError:
            continue
        res = importers.normalize_gene_ids(db, [token], species=species)
        if res["mapped_gene_ids"]:
            gene_id = res["mapped_gene_ids"][0]
            gene = db.get_gene(gene_id)
            if gene is None:
                continue
            species_counts[gene.species] = species_counts.get(gene.species, 0) + 1
            rec = {
                "row_index": idx,
                "gene_id": gene.id,
                "symbol": gene.symbol,
                "species": gene.species,
                "log2fc": round(log2fc, 4),
                "direction": "up" if log2fc > 0 else "down" if log2fc < 0 else "flat",
            }
            if pval_col and (row.get(pval_col) or "").strip():
                try:
                    rec["p_value"] = float(row[pval_col])
                except ValueError:
                    pass
            if qval_col and (row.get(qval_col) or "").strip():
                try:
                    rec["q_value"] = float(row[qval_col])
                except ValueError:
                    pass
            mapped.append(rec)
        elif res["ambiguous_count"]:
            ambiguous += 1
        else:
            unmapped += 1

    guessed_species = species or (max(species_counts, key=species_counts.get) if species_counts else None)
    mapped.sort(key=lambda r: (-abs(r["log2fc"]), r["symbol"]))
    if ambiguous:
        warnings.append(f"{ambiguous} row(s) were ambiguous")
    if unmapped:
        warnings.append(f"{unmapped} row(s) did not map to atlas genes")
    if not mapped:
        warnings.append("no rows mapped cleanly to atlas genes")
    return {
        "mode": "imported_table",
        "filename": filename,
        "species": guessed_species,
        "row_count": len(mapped) + ambiguous + unmapped,
        "mapped_count": len(mapped),
        "ambiguous_count": ambiguous,
        "unmapped_count": unmapped,
        "gene_column": gene_col,
        "logfc_column": logfc_col,
        "pvalue_column": pval_col,
        "qvalue_column": qval_col,
        "results": mapped[:top],
        "warnings": warnings,
    }


def analyze_atlas_contrast(db, species: str, group_a: list[str], group_b: list[str],
                           top: int = 50, min_abs_log2fc: float = 0.0) -> dict[str, Any]:
    mx = expression.get_matrix(species)
    if mx is None:
        return {"mode": "atlas_groups", "species": species, "results": [],
                "warnings": [f"expression data not available for {species}"]}
    available_tissues = sorted(set(s.get("tissue", "unknown") for s in mx.samples))
    idx_a = [i for i, s in enumerate(mx.samples) if s.get("tissue") in group_a]
    idx_b = [i for i, s in enumerate(mx.samples) if s.get("tissue") in group_b]
    if not idx_a or not idx_b:
        warnings = []
        if not idx_a:
            warnings.append(f"group_a tissues not found: {group_a}")
        if not idx_b:
            warnings.append(f"group_b tissues not found: {group_b}")
        return {
            "mode": "atlas_groups",
            "species": species,
            "available_tissues": available_tissues,
            "results": [],
            "warnings": warnings,
        }

    rows = []
    for gene_id, vals in mx.genes.items():
        mean_a = sum(vals[i] for i in idx_a) / len(idx_a)
        mean_b = sum(vals[i] for i in idx_b) / len(idx_b)
        log2fc = math.log2(mean_b + 1.0) - math.log2(mean_a + 1.0)
        if abs(log2fc) < min_abs_log2fc:
            continue
        gene = db.get_gene(gene_id)
        rows.append({
            "gene_id": gene_id,
            "symbol": gene.symbol if gene else gene_id,
            "species": species,
            "mean_group_a": round(mean_a, 4),
            "mean_group_b": round(mean_b, 4),
            "log2fc": round(log2fc, 4),
            "direction": "up" if log2fc > 0 else "down" if log2fc < 0 else "flat",
            "is_tf": bool(gene.is_tf) if gene else False,
        })
    rows.sort(key=lambda r: (-abs(r["log2fc"]), r["symbol"]))
    return {
        "mode": "atlas_groups",
        "species": species,
        "group_a": group_a,
        "group_b": group_b,
        "available_tissues": available_tissues,
        "results": rows[:top],
        "tested_genes": len(rows),
        "warnings": [],
    }
