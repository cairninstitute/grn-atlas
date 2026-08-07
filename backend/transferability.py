"""Cross-species transferability assessment for GRN Atlas."""

from __future__ import annotations

from typing import Any

import context
import evidence
import planning


def _confidence_score(label: str | None) -> float:
    return {
        "high": 1.0,
        "moderate": 0.65,
        "low": 0.3,
        "unsupported": 0.0,
    }.get(label or "unsupported", 0.0)


def _find_orthologs(db, gene_id: str, target_species: str) -> list[dict[str, Any]]:
    cur = db.conn.execute if hasattr(db, "conn") else db.execute
    rows = cur(
        "SELECT gene_a, gene_b, species_a, species_b, rel_type, score "
        "FROM orthologs WHERE (gene_a = ? AND species_b = ?) OR (gene_b = ? AND species_a = ?)",
        (gene_id, target_species, gene_id, target_species),
    ).fetchall()
    out = []
    for row in rows:
        target_gene_id = row["gene_b"] if row["gene_a"] == gene_id else row["gene_a"]
        gene = cur("SELECT id, symbol, species, is_tf FROM genes WHERE id=?", (target_gene_id,)).fetchone()
        if gene:
            out.append({
                "gene_id": gene["id"],
                "symbol": gene["symbol"],
                "species": gene["species"],
                "is_tf": bool(gene["is_tf"]),
                "score": row["score"],
                "rel_type": row["rel_type"],
            })
    return out


def assess_transferability(db, gene_id: str, target_species: str, intent: str = "experiment") -> dict[str, Any]:
    source_audit = evidence.summarize_gene_evidence(db, gene_id)
    source_gene = source_audit.get("summary", {}).get("gene")
    if not source_gene:
        return {
            "title": f"Transferability assessment for {gene_id}",
            "gene_id": gene_id,
            "target_species": target_species,
            "status": "missing_source_gene",
            "notes": [f"Source gene {gene_id} was not found in the atlas."],
        }

    orthologs = _find_orthologs(db, gene_id, target_species)
    target_readiness = context.build_readiness_report(db, target_species, intent)
    ranked_orthologs = []
    if orthologs:
        triage = planning.triage_candidates(db, [o["gene_id"] for o in orthologs], intent=intent, species=target_species, top_n=len(orthologs))
        rank_map = {row["gene_id"]: row for row in triage.get("ranked_candidates", [])}
        for orth in orthologs:
            audit = evidence.summarize_gene_evidence(db, orth["gene_id"])
            ranked_orthologs.append({
                **orth,
                "confidence": audit.get("confidence", {}),
                "evidence_summary": audit.get("evidence_summary", {}),
                "priority_score": rank_map.get(orth["gene_id"], {}).get("priority_score", 0.0),
            })
        ranked_orthologs.sort(key=lambda row: (-row["priority_score"], -(row.get("score") or 0.0), row["gene_id"]))

    best = ranked_orthologs[0] if ranked_orthologs else None
    source_conf = _confidence_score(source_audit.get("confidence", {}).get("label"))
    best_conf = _confidence_score((best or {}).get("confidence", {}).get("label"))
    ortho_score = min(len(ranked_orthologs) / 3.0, 1.0)
    readiness = target_readiness.get("readiness_score", 0.0)
    transferability_score = round((0.35 * source_conf) + (0.25 * best_conf) + (0.25 * readiness) + (0.15 * ortho_score), 3)
    label = "high" if transferability_score >= 0.75 else "moderate" if transferability_score >= 0.5 else "low"

    supported = []
    caveats = []
    validation = []

    if ranked_orthologs:
        supported.append(f"{source_gene['symbol']} has {len(ranked_orthologs)} ortholog candidate(s) in {target_species}.")
        if best:
            if best.get("confidence", {}).get("label") in ("high", "moderate", "low"):
                supported.append(f"Best target ortholog is {best['symbol']} with {best.get('confidence', {}).get('label')} atlas support.")
            else:
                caveats.append(f"best target ortholog {best['symbol']} currently has no direct target-species support in loaded atlas layers")
    else:
        caveats.append(f"no ortholog for {source_gene['symbol']} was found in {target_species}")

    if target_readiness.get("readiness_score", 0.0) >= 0.8:
        supported.append(f"{target_species} has the core layers required for {intent} analysis.")
    else:
        caveats.extend(g["detail"] for g in target_readiness.get("coverage_gaps", [])[:3])

    caveats.append("this assessment is gene-level; direct edge conservation still needs explicit grn-conservation or ortholog-network follow-up")
    if not ranked_orthologs:
        validation.append("confirm orthology or target-species gene mapping before transferring the claim")
    else:
        validation.append(f"audit evidence for {best['symbol']} in {target_species} before transferring conclusions")
        validation.append(f"run species-specific follow-up in {target_species} rather than assuming source-species directionality is preserved")
    if target_readiness.get("available_layers", {}).get("binding_sites", 0) <= 0:
        validation.append(f"add binding or direct regulatory evidence in {target_species} before claiming promoter-level conservation")

    return {
        "title": f"Transferability assessment for {source_gene['symbol']} to {target_species}",
        "intent": intent,
        "source_gene": {"gene_id": source_gene["id"], "symbol": source_gene["symbol"], "species": source_gene["species"]},
        "target_species": target_species,
        "source_confidence": source_audit.get("confidence", {}),
        "target_readiness": target_readiness,
        "ortholog_candidates": ranked_orthologs,
        "best_target_ortholog": best,
        "transferability_score": transferability_score,
        "transferability_label": label,
        "supported_transfer_claims": supported,
        "caveats": caveats,
        "recommended_validation": validation,
    }
