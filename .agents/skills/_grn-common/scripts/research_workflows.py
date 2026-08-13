"""Shared helpers for composite GRN Atlas research workflows."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "backend"))

import main as backend  # type: ignore

from common import run_async


FAMILY_CUE_MAP = {
    "MYB": ["MYB", "AN2", "DPL", "EOBI"],
    "R2R3-MYB": ["MYB", "AN2", "DPL", "EOBI"],
    "R3-MYB": ["MYB", "AN2", "DPL", "EOBI"],
    "BHLH": ["bHLH", "JAF13", "AN1", "EGL3", "EGL"],
    "WD40": ["WD40", "AN11", "TTG1"],
    "DFR": ["DFR"],
    "CHS": ["CHS", "CHSB", "CHSJ"],
    "F3H": ["F3H"],
    "F3'H": ["F3'H", "F3H"],
    "ANTHOCYANIN": ["AN2", "JAF13", "DFR", "CHS"],
    "PIGMENT": ["AN2", "JAF13", "DFR", "CHS"],
    "FLAVONOID": ["AN2", "JAF13", "DFR", "CHS"],
    "ABA": ["ABF", "AREB", "ABI5", "ABI2", "PYL", "SnRK2"],
    "DROUGHT": ["ABF", "AREB", "ABI5", "DREB", "NAC", "MYB"],
    "FLOWERING": ["FLC", "FT", "SOC1", "CO", "LFY"],
    "SCENT": ["ODO1", "EOBI", "EOBII", "MYB", "PAL", "C4H"],
    "VOLATILE": ["ODO1", "EOBI", "EOBII", "PAL", "C4H"],
    "ARCHITECTURE": ["TB1", "BRC1", "TCP", "PIN", "AUX"],
}


def get_backend():
    return backend


def resolve_gene(db, raw_gene: str, species: str | None):
    raw = (raw_gene or "").strip()
    if not raw:
        return None
    gene = db.get_gene(raw)
    if gene:
        return gene
    if species:
        gene = db.find_gene_by_symbol_species(raw, species)
        if gene:
            return gene
    hits = db.search_genes(raw, limit=5, species=species)
    return hits[0] if hits else None


def resolve_gene_ids(raw_genes: list[str], species: str | None) -> tuple[list[dict[str, Any]], list[str]]:
    db = backend.db
    resolved = []
    unresolved = []
    for raw in raw_genes:
        gene = resolve_gene(db, raw, species)
        if not gene:
            unresolved.append(raw)
            continue
        resolved.append({
            "input": raw,
            "gene_id": gene.id,
            "symbol": gene.symbol,
            "species": gene.species,
            "name": gene.name,
            "is_tf": gene.is_tf,
        })
    return resolved, unresolved


def import_and_resolve(content: str, species: str | None, filename: str | None = None) -> dict[str, Any]:
    req = backend.DatasetImportRequest(content=content, species=species, filename=filename)
    return run_async(backend.dataset_import(req))


def extract_gene_ids(import_data: dict[str, Any]) -> list[str]:
    return list(import_data.get("mapped_gene_ids", []) or [])


def derive_family_cues(literature_data: dict[str, Any]) -> list[str]:
    cues: list[str] = []
    for item in (literature_data.get("candidate_summary") or {}).get("candidate_genes", []):
        name = (item.get("name") or "").upper()
        for token in re.split(r"[^A-Z0-9+'-]+", name):
            if not token:
                continue
            if token in {"MYB", "BHLH", "WD40", "DFR", "CHS", "F3H", "F3'H"}:
                cues.append(token)
            elif "MYB" in token:
                cues.append("MYB")
            elif "BHLH" in token or "EGL" in token or "JAF13" in token:
                cues.append("BHLH")
            elif "DFR" in token:
                cues.append("DFR")
            elif "CHS" in token:
                cues.append("CHS")
    for item in (literature_data.get("candidate_summary") or {}).get("mechanisms", []):
        name = (item.get("name") or "").upper()
        for key in FAMILY_CUE_MAP:
            if key in name:
                cues.append(key)
    deduped = []
    seen = set()
    for cue in cues:
        if cue not in seen:
            deduped.append(cue)
            seen.add(cue)
    return deduped


def rescue_candidates_from_family_cues(species: str, cues: list[str], limit_per_query: int = 6) -> list[dict[str, Any]]:
    db = backend.db
    rescued: list[dict[str, Any]] = []
    seen_gene_ids = set()
    for cue in cues:
        queries = FAMILY_CUE_MAP.get(cue.upper(), [cue])
        for query in queries:
            for gene in db.search_genes(query, limit=limit_per_query, species=species):
                if gene.id in seen_gene_ids:
                    continue
                rescued.append({
                    "gene_id": gene.id,
                    "symbol": gene.symbol,
                    "species": gene.species,
                    "matched_via": cue,
                    "match_query": query,
                    "is_tf": gene.is_tf,
                })
                seen_gene_ids.add(gene.id)
    return rescued


def classify_phenotype_domain(phenotype: str) -> dict[str, Any]:
    text = (phenotype or "").lower()
    if any(t in text for t in ["color", "colour", "pigment", "anthocyanin", "flavonoid", "flower color"]):
        return {"phenotype_domain": "pigmentation", "ranking_profile": "trait_regulator_intervention", "candidate_generation_mode": "pigment_regulator_family"}
    if any(t in text for t in ["aba", "drought", "stress", "water deficit"]):
        return {"phenotype_domain": "stress_response", "ranking_profile": "stress_regulator_intervention", "candidate_generation_mode": "stress_signal_family"}
    if any(t in text for t in ["flowering", "flower time", "bolting", "vernalization"]):
        return {"phenotype_domain": "flowering_time", "ranking_profile": "developmental_regulator_intervention", "candidate_generation_mode": "flowering_time_family"}
    if any(t in text for t in ["scent", "volatile", "fragrance", "odor", "odour"]):
        return {"phenotype_domain": "scent", "ranking_profile": "metabolic_regulator_intervention", "candidate_generation_mode": "volatile_pathway_family"}
    if any(t in text for t in ["architecture", "branch", "branching", "height", "internode", "growth habit"]):
        return {"phenotype_domain": "growth_architecture", "ranking_profile": "developmental_regulator_intervention", "candidate_generation_mode": "architecture_regulator_family"}
    return {"phenotype_domain": "generic_trait", "ranking_profile": "generic_trait_intervention", "candidate_generation_mode": "literature_first_generic"}


def family_level_analogs(species: str, source_symbol: str | None, limit: int = 8) -> list[dict[str, Any]]:
    if not species:
        return []
    cues = []
    src = (source_symbol or "").upper()
    if "MYB" in src:
        cues.append("MYB")
    if "BHLH" in src or "EGL" in src or "JAF13" in src:
        cues.append("BHLH")
    if "WD40" in src or "TTG1" in src or "AN11" in src:
        cues.append("WD40")
    if "DFR" in src:
        cues.append("DFR")
    if "CHS" in src:
        cues.append("CHS")
    if "ABF" in src or "ABI" in src or "AREB" in src:
        cues.append("ABA")
    if "FLC" in src or "FT" in src or "SOC1" in src:
        cues.append("FLOWERING")
    if "ODO" in src or "EOB" in src:
        cues.append("SCENT")
    rescued = rescue_candidates_from_family_cues(species, cues, limit_per_query=limit)
    return rescued[:limit]


def detect_columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = []
    for row in rows:
        extra = row.get("extra") or {}
        for k in extra.keys():
            if k not in keys:
                keys.append(k)
    detected = [{"column": "gene_token", "role_guess": "gene_identifier"}]
    if any(row.get("score") not in (None, "") for row in rows):
        detected.append({"column": "score", "role_guess": "primary_score_or_logfc"})
    for k in keys:
        kl = k.lower()
        if "padj" in kl or "fdr" in kl or "qval" in kl:
            role = "adjusted_p_value"
        elif "pval" in kl or k.lower() == "p":
            role = "p_value"
        elif "note" in kl or "comment" in kl:
            role = "annotation"
        else:
            role = "extra_metadata"
        detected.append({"column": k, "role_guess": role})
    return detected


def infer_deg_schema(rows: list[dict[str, Any]]) -> dict[str, Any]:
    detected = detect_columns(rows)
    roles = {item["column"]: item["role_guess"] for item in detected}
    has_score = any(item["role_guess"] == "primary_score_or_logfc" for item in detected)
    has_adj = any(item["role_guess"] == "adjusted_p_value" for item in detected)
    schema = "tabular_gene_set"
    if has_score and has_adj:
        schema = "deg_table_like"
    elif has_score:
        schema = "ranked_gene_table_like"
    return {"schema_guess": schema, "column_roles": roles}


def build_execution_design(intent: str, species: str | None, strategies: list[dict[str, Any]]) -> dict[str, Any]:
    top = strategies[0] if strategies else None
    if not top:
        return {
            "recommended_controls": [],
            "suggested_readouts": [],
            "replicate_heuristics": [],
            "success_criteria": [],
            "failure_modes": [],
        }
    assay = (top.get("assay_class") or "").lower()
    controls = ["matched untreated control", "target-free negative control"]
    readouts = ["candidate-gene expression change", "downstream marker response"]
    replicates = ["minimum 3 biological replicates for first-pass validation"]
    success = [f"signal should be detectable within the expected {top.get('time_tier_days', 'short')} day window"]
    failure = ["no measurable target-linked readout change", "effect only appears in unsupported contexts"]
    if assay == "rnai":
        controls.append("non-targeting dsRNA control")
        readouts.append("on-target knockdown specificity check")
        failure.append("strong off-target signature or poor specificity")
    elif assay == "expression":
        readouts.append("tissue/context differential expression consistency")
    elif assay == "in_silico":
        readouts.append("network perturbation consistency across evidence layers")
    return {
        "species": species,
        "intent": intent,
        "primary_strategy": top.get("strategy") or top.get("experiment"),
        "recommended_controls": controls,
        "suggested_readouts": readouts,
        "replicate_heuristics": replicates,
        "success_criteria": success,
        "failure_modes": failure,
    }


def build_experiment_strategy_summary(ranked_experiments: list[dict[str, Any]]) -> dict[str, Any]:
    by_strategy: dict[str, dict[str, Any]] = {}
    for item in ranked_experiments or []:
        strategy = item.get("experiment") or item.get("assay_class") or "unknown"
        score = float(item.get("optimized_priority_score", 0.0) or 0.0)
        current = by_strategy.get(strategy)
        if current is None or score > float(current.get("optimized_priority_score", 0.0) or 0.0):
            by_strategy[strategy] = item
    ranked = sorted(
        [
            {
                "strategy": key,
                "gene_id": value.get("gene_id"),
                "symbol": value.get("symbol"),
                "assay_class": value.get("assay_class"),
                "optimized_priority_score": value.get("optimized_priority_score"),
                "cost_tier": value.get("cost_tier"),
                "time_tier_days": value.get("time_tier_days"),
                "rationale": value.get("rationale"),
                "constraint_notes": value.get("constraint_notes", []),
                "recommended_skills": value.get("recommended_skills", []),
            }
            for key, value in by_strategy.items()
        ],
        key=lambda x: (-float(x.get("optimized_priority_score", 0.0) or 0.0), str(x.get("strategy"))),
    )
    return {
        "ranked_strategies": ranked,
        "recommended_first_action": ranked[0] if ranked else None,
        "fallback_action": ranked[1] if len(ranked) > 1 else None,
    }
