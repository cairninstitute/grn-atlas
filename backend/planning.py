"""Planning and prioritization helpers for GRN Atlas research workflows."""

from __future__ import annotations

from typing import Any

import context
import evidence


def _normalize_id_list(gene_ids: list[str]) -> list[str]:
    seen = set()
    out = []
    for gene_id in gene_ids:
        if not gene_id:
            continue
        gene_id = gene_id.strip()
        if gene_id and gene_id not in seen:
            seen.add(gene_id)
            out.append(gene_id)
    return out


def _intent_weights(intent: str) -> dict[str, float]:
    weights = {
        "curated": 0.30,
        "motif": 0.10,
        "expression": 0.10,
        "pathway": 0.05,
        "trait": 0.05,
        "orthology": 0.10,
        "tf": 0.10,
        "readiness": 0.20,
    }
    if intent == "rnai":
        return {
            "curated": 0.15,
            "motif": 0.05,
            "expression": 0.25,
            "pathway": 0.10,
            "trait": 0.00,
            "orthology": 0.05,
            "tf": 0.05,
            "readiness": 0.35,
        }
    if intent == "traits":
        return {
            "curated": 0.15,
            "motif": 0.05,
            "expression": 0.00,
            "pathway": 0.10,
            "trait": 0.35,
            "orthology": 0.05,
            "tf": 0.05,
            "readiness": 0.25,
        }
    if intent == "network":
        return {
            "curated": 0.35,
            "motif": 0.10,
            "expression": 0.05,
            "pathway": 0.05,
            "trait": 0.00,
            "orthology": 0.10,
            "tf": 0.15,
            "readiness": 0.20,
        }
    return weights


def _score_components(audit: dict[str, Any], readiness: dict[str, Any], intent: str) -> dict[str, float]:
    counts = audit.get("evidence_summary", {}).get("support_counts", {})
    gene = audit.get("summary", {}).get("gene", {}) or {}
    ortholog_count = audit.get("summary", {}).get("ortholog_count", 0)
    weights = _intent_weights(intent)
    components = {
        "curated": min(counts.get("curated", 0) / 50.0, 1.0),
        "motif": min(counts.get("motif_supported", 0) / 10.0, 1.0),
        "expression": 1.0 if counts.get("coexpression_supported", 0) > 0 else 0.0,
        "pathway": min(counts.get("pathway_supported", 0) / 50.0, 1.0),
        "trait": min(counts.get("trait_supported", 0) / 100.0, 1.0),
        "orthology": min(ortholog_count / 5.0, 1.0),
        "tf": 1.0 if gene.get("is_tf") else 0.0,
        "readiness": readiness.get("readiness_score", 0.0),
    }
    components["priority_score"] = round(
        sum(components[name] * weight for name, weight in weights.items()),
        3,
    )
    return components


def _candidate_reasons(audit: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    counts = audit.get("evidence_summary", {}).get("support_counts", {})
    gene = audit.get("summary", {}).get("gene", {}) or {}
    reasons = []
    if gene.get("is_tf"):
        reasons.append("gene is a transcription factor")
    if counts.get("curated", 0):
        reasons.append(f"has {counts['curated']} curated interaction record(s)")
    if counts.get("motif_supported", 0):
        reasons.append(f"has {counts['motif_supported']} motif-supported signal(s)")
    if counts.get("coexpression_supported", 0):
        reasons.append("has expression/coexpression support")
    if counts.get("trait_supported", 0):
        reasons.append(f"has {counts['trait_supported']} trait association(s)")
    if counts.get("pathway_supported", 0):
        reasons.append(f"has {counts['pathway_supported']} pathway annotation(s)")
    if readiness.get("coverage_gaps"):
        reasons.append(f"{len(readiness['coverage_gaps'])} coverage gap(s) may constrain follow-up")
    return reasons


def triage_candidates(db, gene_ids: list[str], intent: str = "experiment",
                      species: str | None = None, top_n: int = 10) -> dict[str, Any]:
    ranked = []
    missing = []
    for gene_id in _normalize_id_list(gene_ids):
        audit = evidence.summarize_gene_evidence(db, gene_id)
        gene = audit.get("summary", {}).get("gene")
        if not gene:
            missing.append({"gene_id": gene_id, "status": "missing"})
            continue
        gene_species = gene.get("species")
        if species and gene_species != species:
            missing.append({"gene_id": gene_id, "status": "species_mismatch", "species": gene_species})
            continue
        readiness = context.build_readiness_report(db, gene_species, intent, gene_id)
        components = _score_components(audit, readiness, intent)
        ranked.append({
            "gene_id": gene["id"],
            "symbol": gene.get("symbol"),
            "species": gene_species,
            "priority_score": components.pop("priority_score"),
            "score_components": components,
            "confidence": audit.get("confidence", {}),
            "recommended_skills": readiness.get("recommended_skills", []),
            "coverage_gaps": readiness.get("coverage_gaps", []),
            "reasons": _candidate_reasons(audit, readiness),
            "evidence_summary": audit.get("evidence_summary", {}),
        })
    ranked.sort(key=lambda row: (-row["priority_score"], row["symbol"] or row["gene_id"]))
    return {
        "intent": intent,
        "species": species,
        "input_gene_count": len(_normalize_id_list(gene_ids)),
        "ranked_candidates": ranked[:max(top_n, 1)],
        "excluded_genes": missing,
    }


def _experiment_options_for_gene(audit: dict[str, Any], readiness: dict[str, Any], intent: str) -> list[dict[str, Any]]:
    gene = audit.get("summary", {}).get("gene", {}) or {}
    counts = audit.get("evidence_summary", {}).get("support_counts", {})
    species = gene.get("species")
    options = []

    if readiness.get("available_layers", {}).get("network_edges", 0) > 0:
        score = 0.55 + (0.15 if gene.get("is_tf") else 0.0) + min(counts.get("curated", 0) / 40.0, 0.2)
        options.append({
            "experiment": "network_perturbation",
            "priority_score": round(min(score, 0.99), 3),
            "rationale": "network structure is available, so perturbation effects can be estimated from signed paths.",
            "recommended_skills": ["grn-perturbation", "grn-network", "grn-evidence-audit"],
        })

    if readiness.get("available_layers", {}).get("expression_samples", 0) > 0:
        score = 0.45 + (0.10 if counts.get("coexpression_supported", 0) > 0 else 0.0)
        options.append({
            "experiment": "expression_context_review",
            "priority_score": round(min(score, 0.95), 3),
            "rationale": "expression coverage exists for this species, so tissue/context specificity can be checked before intervention.",
            "recommended_skills": ["grn-expression", "grn-coexpression", "grn-diff-regulation"],
        })

    if readiness.get("available_layers", {}).get("binding_sites", 0) > 0 and gene.get("is_tf"):
        score = 0.40 + min(counts.get("motif_supported", 0) / 20.0, 0.25)
        options.append({
            "experiment": "motif_binding_validation",
            "priority_score": round(min(score, 0.9), 3),
            "rationale": "binding-site context is available and the gene is a TF, so promoter-level follow-up is feasible.",
            "recommended_skills": ["grn-motif", "grn-export", "grn-evidence-audit"],
        })

    if species in ("petunia", "tomato", "arabidopsis") and readiness.get("available_layers", {}).get("expression_samples", 0) > 0:
        score = 0.40 + (0.10 if intent == "rnai" else 0.0) + (0.10 if readiness.get("available_layers", {}).get("network_edges", 0) > 0 else 0.0)
        options.append({
            "experiment": "dsrna_design",
            "priority_score": round(min(score, 0.9), 3),
            "rationale": "plant transcriptome support is available, enabling dsRNA specificity and downstream knockdown checks.",
            "recommended_skills": ["grn-dsrna", "grn-dsrna-screen", "grn-perturbation"],
        })

    if counts.get("trait_supported", 0) > 0:
        score = 0.35 + min(counts.get("trait_supported", 0) / 50.0, 0.25)
        options.append({
            "experiment": "trait_association_followup",
            "priority_score": round(min(score, 0.85), 3),
            "rationale": "trait associations are loaded for this gene, so phenotype-oriented follow-up is justified.",
            "recommended_skills": ["grn-enrichment", "grn-evidence-audit"],
        })

    if audit.get("summary", {}).get("ortholog_count", 0) > 0:
        score = 0.30 + min(audit["summary"]["ortholog_count"] / 10.0, 0.20)
        options.append({
            "experiment": "cross_species_conservation_check",
            "priority_score": round(min(score, 0.8), 3),
            "rationale": "ortholog context exists, so conservation can be used to judge transferability across species.",
            "recommended_skills": ["grn-orthology", "grn-conservation"],
        })

    options.sort(key=lambda row: (-row["priority_score"], row["experiment"]))
    return options


def prioritize_experiments(db, gene_ids: list[str], intent: str = "experiment",
                           species: str | None = None, max_recommendations: int = 5) -> dict[str, Any]:
    triage = triage_candidates(db, gene_ids, intent=intent, species=species, top_n=max(len(gene_ids), 1))
    plans = []
    for candidate in triage["ranked_candidates"]:
        audit = evidence.summarize_gene_evidence(db, candidate["gene_id"])
        readiness = context.build_readiness_report(db, candidate["species"], intent, candidate["gene_id"])
        plans.append({
            "gene_id": candidate["gene_id"],
            "symbol": candidate["symbol"],
            "species": candidate["species"],
            "candidate_priority_score": candidate["priority_score"],
            "confidence": candidate["confidence"],
            "recommended_experiments": _experiment_options_for_gene(audit, readiness, intent)[:max(max_recommendations, 1)],
            "coverage_gaps": readiness.get("coverage_gaps", []),
        })
    return {
        "intent": intent,
        "species": species,
        "candidate_count": len(plans),
        "plans": plans,
        "excluded_genes": triage.get("excluded_genes", []),
    }
