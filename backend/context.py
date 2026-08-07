"""Coverage and readiness helpers for GRN Atlas analyses."""

from __future__ import annotations

from typing import Any

import expression


ASSEMBLY_OF = {"tomato": "SL4.0", "petunia": "Peaxi162v1.6.2", "arabidopsis": "TAIR10"}

INTENT_REQUIREMENTS = {
    "network": {"required": ["network_edges"], "optional": ["orthologs"]},
    "expression": {"required": ["expression_samples"], "optional": ["network_edges"]},
    "motif": {"required": ["binding_sites"], "optional": ["network_edges"]},
    "perturbation": {"required": ["network_edges"], "optional": ["expression_samples"]},
    "orthology": {"required": ["orthologs"], "optional": ["network_edges"]},
    "traits": {"required": ["trait_associations"], "optional": []},
    "rnai": {"required": ["expression_samples"], "optional": ["network_edges"]},
    "experiment": {"required": ["network_edges"], "optional": ["expression_samples", "binding_sites", "trait_associations"]},
}

RECOMMENDED_SKILLS = {
    "network": ["grn-network", "grn-pathfinding", "grn-regulon"],
    "expression": ["grn-expression", "grn-coexpression", "grn-diff-regulation"],
    "motif": ["grn-motif", "grn-evidence-audit"],
    "perturbation": ["grn-perturbation", "grn-upstream", "grn-evidence-audit"],
    "orthology": ["grn-orthology", "grn-conservation"],
    "traits": ["grn-enrichment", "grn-candidate-triage"],
    "rnai": ["grn-dsrna", "grn-dsrna-screen", "grn-experiment-prioritization"],
    "experiment": ["grn-candidate-triage", "grn-experiment-prioritization", "grn-evidence-audit"],
}


def get_species_layer_counts(db, species: str) -> dict[str, Any]:
    cur = db.conn.execute if hasattr(db, "conn") else db.execute
    assembly = ASSEMBLY_OF.get(species)
    genes = cur("SELECT COUNT(*) FROM genes WHERE species=?", (species,)).fetchone()[0]
    measured = cur(
        "SELECT COUNT(*) FROM interactions i JOIN genes t ON t.id=i.target_id "
        "WHERE t.species=? AND i.sources NOT LIKE '%Inferred%'",
        (species,),
    ).fetchone()[0]
    inferred = cur(
        "SELECT COUNT(*) FROM interactions i JOIN genes t ON t.id=i.target_id "
        "WHERE t.species=? AND i.sources LIKE '%Inferred%'",
        (species,),
    ).fetchone()[0]
    orthologs = cur(
        "SELECT COUNT(*) FROM orthologs o JOIN genes g ON g.id=o.gene_a WHERE g.species=?",
        (species,),
    ).fetchone()[0]
    binding = cur("SELECT COUNT(*) FROM motif_hits WHERE assembly=?", (assembly,)).fetchone()[0] if assembly else 0
    pathways = cur(
        "SELECT COUNT(*) FROM pathway_annotations a JOIN genes g ON g.id=a.gene_id WHERE g.species=?",
        (species,),
    ).fetchone()[0]
    traits = cur(
        "SELECT COUNT(*) FROM trait_associations a JOIN genes g ON g.id=a.gene_id WHERE g.species=?",
        (species,),
    ).fetchone()[0]
    emx = expression.get_matrix(species) if species in expression.species_with_expression() else None
    return {
        "assembly": assembly,
        "genes": genes,
        "network_edges": measured + inferred,
        "measured_edges": measured,
        "inferred_edges": inferred,
        "orthologs": orthologs,
        "binding_sites": binding,
        "expression_samples": emx.n if emx else 0,
        "pathway_annotations": pathways,
        "trait_associations": traits,
    }


def build_coverage_gaps(species: str, intent: str, layer_counts: dict[str, Any]) -> list[dict[str, Any]]:
    req = INTENT_REQUIREMENTS.get(intent, {"required": [], "optional": []})
    gaps = []
    for layer in req["required"]:
        if layer_counts.get(layer, 0) <= 0:
            gaps.append({
                "layer": layer,
                "importance": "required",
                "status": "missing",
                "detail": f"{species} has no loaded {layer} for {intent} analysis.",
            })
    for layer in req["optional"]:
        if layer_counts.get(layer, 0) <= 0:
            gaps.append({
                "layer": layer,
                "importance": "optional",
                "status": "missing",
                "detail": f"{species} is missing optional {layer}; results may be narrower.",
            })
    return gaps


def build_readiness_report(db, species: str, intent: str, gene_id: str | None = None) -> dict[str, Any]:
    counts = get_species_layer_counts(db, species)
    if counts["genes"] <= 0:
        return {
            "species": species,
            "intent": intent,
            "readiness_score": 0.0,
            "available_layers": counts,
            "missing_layers": [{"layer": "genes", "importance": "required", "status": "missing"}],
            "coverage_gaps": [{"layer": "genes", "importance": "required", "status": "missing", "detail": f"{species} is not present in the atlas."}],
            "recommended_skills": [],
            "notes": [f"Species {species} is not present in the current atlas."],
        }

    req = INTENT_REQUIREMENTS.get(intent)
    if req is None:
        return {
            "species": species,
            "intent": intent,
            "readiness_score": 0.0,
            "available_layers": counts,
            "missing_layers": [{"layer": "intent", "importance": "required", "status": "unsupported"}],
            "coverage_gaps": [{"layer": "intent", "importance": "required", "status": "unsupported", "detail": f"Unknown intent '{intent}'."}],
            "recommended_skills": [],
            "notes": [f"Intent '{intent}' is not recognized."],
        }

    coverage_gaps = build_coverage_gaps(species, intent, counts)
    required = req["required"]
    optional = req["optional"]
    req_hits = sum(1 for layer in required if counts.get(layer, 0) > 0)
    opt_hits = sum(1 for layer in optional if counts.get(layer, 0) > 0)
    req_score = req_hits / len(required) if required else 1.0
    opt_score = opt_hits / len(optional) if optional else 1.0
    readiness = round((0.8 * req_score) + (0.2 * opt_score), 3)
    missing_layers = [
        {"layer": layer, "importance": "required" if layer in required else "optional", "status": "missing"}
        for layer in required + optional if counts.get(layer, 0) <= 0
    ]

    notes = []
    if not coverage_gaps:
        notes.append(f"{species} has the expected core layers for {intent} analysis.")
    else:
        notes.append(f"{species} is missing {len(coverage_gaps)} layer(s) relevant to {intent} analysis.")
    if gene_id:
        notes.append(f"Report requested in the context of gene {gene_id}.")
    return {
        "species": species,
        "intent": intent,
        "gene_id": gene_id,
        "readiness_score": readiness,
        "available_layers": counts,
        "missing_layers": missing_layers,
        "coverage_gaps": coverage_gaps,
        "recommended_skills": RECOMMENDED_SKILLS.get(intent, []),
        "notes": notes,
    }
