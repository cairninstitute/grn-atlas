"""Advanced context-analysis and onboarding helpers."""

from __future__ import annotations

from itertools import combinations
from typing import Any

import context

_PERTURB_DECAY = 0.7
_EDGE_SIGN = {"activation": 1, "repression": -1, "regulation": 0, "unknown": 0}


def _run_combo(db, combo: list[dict[str, str]], depth: int = 3, min_confidence: float = 0.0,
               include_inferred: bool = True, min_effect: float = 0.05) -> dict[str, Any]:
    seeds = {}
    for iv in combo:
        g = db.get_gene(iv["gene_id"])
        if not g:
            continue
        seeds[iv["gene_id"]] = (-1 if iv["action"] == "ko" else 1, g.symbol)
    best: dict[str, dict[str, Any]] = {}
    frontier = [(gid, s, 1.0, 0, [sym], False, False) for gid, (s, sym) in seeds.items()]
    while frontier:
        gid, sign, mag, level, path, inf, unknown = frontier.pop()
        if level >= depth:
            continue
        for t in db.get_targets(gid, min_confidence=min_confidence, include_inferred=include_inferred):
            esign = _EDGE_SIGN.get(t.regulation_type, 0)
            n_unknown = unknown or esign == 0
            n_sign = sign * (esign if esign else 1)
            n_mag = mag * max(t.confidence, 0.01) * _PERTURB_DECAY
            if n_mag < min_effect:
                continue
            prev = best.get(t.id)
            if t.id not in seeds and (prev is None or n_mag > prev["magnitude"]):
                best[t.id] = {"symbol": t.symbol, "magnitude": round(n_mag, 4), "sign": n_sign, "unknown": n_unknown}
            if prev is None or n_mag > prev["magnitude"]:
                frontier.append((t.id, n_sign, n_mag, level + 1, path + [t.symbol], inf, n_unknown))
    effects = [
        {"gene_id": gid, "symbol": e["symbol"], "direction": "unknown" if e["unknown"] else ("up" if e["sign"] > 0 else "down"), "magnitude": e["magnitude"]}
        for gid, e in best.items()
    ]
    return {
        "combo": combo,
        "affected_genes": len(effects),
        "up": sum(1 for e in effects if e["direction"] == "up"),
        "down": sum(1 for e in effects if e["direction"] == "down"),
        "unknown": sum(1 for e in effects if e["direction"] == "unknown"),
        "score": round(sum(e["magnitude"] for e in effects[:20]), 4),
        "top_effects": sorted(effects, key=lambda e: -e["magnitude"])[:10],
    }


def combinatorial_perturbation(db, gene_ids: list[str], action: str = "ko", combo_size: int = 2,
                               species: str | None = None, top: int = 10) -> dict[str, Any]:
    valid = []
    excluded = []
    for gene_id in gene_ids:
        gene = db.get_gene(gene_id)
        if not gene:
            excluded.append({"gene_id": gene_id, "status": "missing"})
            continue
        if species and gene.species != species:
            excluded.append({"gene_id": gene_id, "status": "species_mismatch", "species": gene.species})
            continue
        valid.append(gene_id)
    combos = []
    for ids in combinations(valid, min(combo_size, max(len(valid), 1))):
        combo = [{"gene_id": gid, "action": action} for gid in ids]
        combos.append(_run_combo(db, combo))
    combos.sort(key=lambda c: (-c["score"], -c["affected_genes"]))
    return {
        "species": species,
        "action": action,
        "combo_size": combo_size,
        "ranked_combinations": combos[:top],
        "excluded_genes": excluded,
        "warnings": [] if combos else ["not enough valid genes to build the requested combination size"],
    }


def celltype_regulation(db, species: str, gene_ids: list[str] | None = None) -> dict[str, Any]:
    readiness = context.build_readiness_report(db, species, "expression", gene_ids[0] if gene_ids else None)
    return {
        "species": species,
        "supported": False,
        "reason": "Cell-type / single-cell regulatory analysis is not currently supported because the atlas does not yet store cell-type-resolved or single-cell layers.",
        "current_expression_readiness": readiness,
        "required_layers": ["single_cell_expression", "cell_type_annotations", "cell_type_regulatory_edges"],
        "recommended_next_steps": [
            "load cell-type or single-cell expression matrices",
            "attach cell annotations and marker metadata",
            "derive or ingest cell-type-resolved regulatory edges before using this workflow",
        ],
        "requested_gene_ids": gene_ids or [],
    }


def trajectory_regulation(db, species: str, gene_ids: list[str] | None = None) -> dict[str, Any]:
    readiness = context.build_readiness_report(db, species, "expression", gene_ids[0] if gene_ids else None)
    return {
        "species": species,
        "supported": False,
        "reason": "Trajectory / time-series regulatory analysis is not currently supported because the atlas does not yet store pseudotime or longitudinal expression layers.",
        "current_expression_readiness": readiness,
        "required_layers": ["time_series_expression", "trajectory_annotations", "trajectory_regulatory_edges"],
        "recommended_next_steps": [
            "load ordered time-series or pseudotime-resolved samples",
            "attach trajectory stage annotations",
            "derive stage-specific or time-varying regulatory relationships",
        ],
        "requested_gene_ids": gene_ids or [],
    }


def species_onboarding_plan(species_name: str, intended_capabilities: list[str] | None = None) -> dict[str, Any]:
    intended = intended_capabilities or ["network", "expression", "motif", "orthology", "rnai"]
    capability_to_requirements = {
        "network": ["gene models", "curated or inferred regulatory edges"],
        "expression": ["CDS FASTA", "curated RNA-seq panel", "expression matrix"],
        "motif": ["genome FASTA", "annotation GFF", "motif scan outputs"],
        "orthology": ["ortholog table against supported species"],
        "rnai": ["transcript FASTA", "expression matrix"],
        "traits": ["gene-mapped trait or GWAS table"],
    }
    requirements = []
    for cap in intended:
        requirements.extend(capability_to_requirements.get(cap, []))
    deduped = []
    seen = set()
    for req in requirements:
        if req not in seen:
            seen.add(req)
            deduped.append(req)
    return {
        "species_name": species_name,
        "intended_capabilities": intended,
        "minimum_requirements": deduped,
        "staged_plan": [
            {"step": 1, "title": "Load genes and coordinates", "details": "Add gene models, names, species tag, and chromosome coordinates."},
            {"step": 2, "title": "Add sequence context", "details": "Load promoter/gene-body windows and motif hits if genome FASTA + GFF are available."},
            {"step": 3, "title": "Add expression", "details": "Build expression_<species>.json.gz from a curated RNA-seq panel."},
            {"step": 4, "title": "Add orthology", "details": "Load ortholog pairs so conservation and transferability features work."},
            {"step": 5, "title": "Add optional traits and RNAi layers", "details": "Trait tables and transcript FASTA unlock trait and RNAi workflows."},
        ],
        "note": "This plan reflects the existing ONBOARDING_SPECIES runbook and the current atlas architecture.",
    }
