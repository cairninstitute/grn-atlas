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


def _has_scrna_data(db, species: str) -> bool:
    try:
        return db.conn.execute(
            "SELECT COUNT(*) FROM scrna_datasets WHERE species = ?", (species,)
        ).fetchone()[0] > 0
    except Exception:
        return False


def _get_scrna_clusters(db, species: str) -> list[dict]:
    dataset_id = f"scrna_{species}"
    rows = db.conn.execute(
        "SELECT cluster_id, cluster_name, n_cells FROM scrna_clusters "
        "WHERE dataset_id = ? ORDER BY cluster_id", (dataset_id,)
    ).fetchall()
    return [{"cluster_id": r[0], "cluster_name": r[1], "n_cells": r[2]} for r in rows]


def _cluster_expressed_genes(db, species: str, cluster_id: str, min_expr: float = 0.1) -> dict[str, float]:
    dataset_id = f"scrna_{species}"
    rows = db.conn.execute(
        "SELECT gene_id, mean_expression FROM scrna_cluster_expression "
        "WHERE dataset_id = ? AND cluster_id = ? AND mean_expression >= ?",
        (dataset_id, cluster_id, min_expr),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _score_tf_activity(db, species: str, expressed_genes: dict[str, float],
                       min_confidence: float = 0.4, top: int = 25) -> list[dict]:
    gene_set = set(expressed_genes)
    if not gene_set:
        return []

    gene_list = list(gene_set)
    tfs_set: set[tuple[str, str]] = set()
    batch_size = 500
    for batch_start in range(0, len(gene_list), batch_size):
        batch = gene_list[batch_start:batch_start + batch_size]
        placeholders = ",".join("?" * len(batch))
        rows = db.conn.execute(
            f"SELECT DISTINCT i.source_id, g.symbol FROM interactions i "
            f"JOIN genes g ON g.id = i.source_id "
            f"WHERE g.species = ? AND i.confidence >= ? AND i.target_id IN ({placeholders})",
            [species, min_confidence] + batch
        ).fetchall()
        tfs_set.update((r[0], r[1]) for r in rows)
    tfs = list(tfs_set)

    total_expr = sum(expressed_genes.values()) or 1.0
    results = []

    for tf_id, tf_symbol in tfs:
        targets = db.conn.execute(
            "SELECT target_id, confidence, regulation_type FROM interactions "
            "WHERE source_id = ? AND confidence >= ?",
            (tf_id, min_confidence)
        ).fetchall()
        overlap = [(t, c, r) for t, c, r in targets if t in gene_set]
        if not overlap:
            continue

        regulon_size = len(targets)
        overlap_count = len(overlap)
        recall = overlap_count / max(1, len(gene_set))
        precision = overlap_count / max(1, regulon_size)
        overlap_conf = sum(c for _, c, _ in overlap) / overlap_count
        overlap_expr = sum(expressed_genes.get(t, 0.0) for t, _, _ in overlap)
        expr_fraction = overlap_expr / total_expr
        tf_expr = expressed_genes.get(tf_id, 0.0)

        n_activating = sum(1 for _, _, r in overlap if r == "activation")
        n_repressing = sum(1 for _, _, r in overlap if r == "repression")
        dominant_mode = "activator" if n_activating > n_repressing else (
            "repressor" if n_repressing > n_activating else "mixed")

        score = (
            overlap_conf * (overlap_count ** 0.5) * recall
            + 0.4 * precision
            + 0.6 * expr_fraction
            + (0.4 if tf_id in gene_set else 0.0)
            + min(tf_expr / 10.0, 0.4)
        )
        results.append({
            "gene_id": tf_id, "symbol": tf_symbol, "regulon_size": regulon_size,
            "overlap": overlap_count, "recall": round(recall, 4),
            "precision": round(precision, 4),
            "mean_overlap_confidence": round(overlap_conf, 4),
            "explained_expression_fraction": round(expr_fraction, 4),
            "score": round(score, 4), "expressed": tf_id in gene_set,
            "tf_mean_expr": round(tf_expr, 4),
            "dominant_mode": dominant_mode,
            "n_activating": n_activating, "n_repressing": n_repressing,
            "overlap_genes": [t for t, _, _ in overlap[:20]],
        })

    results.sort(key=lambda x: -x["score"])
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results[:top]


def celltype_regulation(db, species: str, gene_ids: list[str] | None = None) -> dict[str, Any]:
    if not _has_scrna_data(db, species):
        readiness = context.build_readiness_report(db, species, "expression", gene_ids[0] if gene_ids else None)
        return {
            "species": species,
            "supported": False,
            "reason": "No scRNA-seq data loaded for this species. Run: make scrna-data",
            "current_expression_readiness": readiness,
            "required_layers": ["scrna_datasets", "scrna_cluster_expression"],
            "requested_gene_ids": gene_ids or [],
        }

    clusters = _get_scrna_clusters(db, species)
    cluster_results = []

    for cluster in clusters:
        expressed = _cluster_expressed_genes(db, species, cluster["cluster_id"])
        regulators = _score_tf_activity(db, species, expressed)

        cluster_results.append({
            "cluster_id": cluster["cluster_id"],
            "cluster_name": cluster["cluster_name"],
            "n_cells": cluster["n_cells"],
            "n_expressed_genes": len(expressed),
            "top_regulators": regulators[:10],
        })

    all_tfs = {}
    for cr in cluster_results:
        for reg in cr["top_regulators"]:
            tid = reg["gene_id"]
            if tid not in all_tfs:
                all_tfs[tid] = {"gene_id": tid, "symbol": reg["symbol"], "clusters": []}
            all_tfs[tid]["clusters"].append({
                "cluster_id": cr["cluster_id"],
                "score": reg["score"],
                "overlap": reg["overlap"],
            })

    specificity_ranked = []
    for tf_id, info in all_tfs.items():
        scores = [c["score"] for c in info["clusters"]]
        max_score = max(scores)
        mean_score = sum(scores) / len(scores)
        specificity = max_score / (mean_score + 0.01)
        specificity_ranked.append({
            **info,
            "max_score": round(max_score, 4),
            "specificity": round(specificity, 4),
            "n_clusters_active": len(info["clusters"]),
        })
    specificity_ranked.sort(key=lambda x: -x["specificity"])

    result = {
        "species": species,
        "supported": True,
        "n_clusters": len(clusters),
        "cluster_regulation": cluster_results,
        "celltype_specific_tfs": specificity_ranked[:25],
        "requested_gene_ids": gene_ids or [],
    }

    if gene_ids:
        gene_set = set(gene_ids)
        gene_clusters = {}
        for cluster in clusters:
            expressed = _cluster_expressed_genes(db, species, cluster["cluster_id"])
            for gid in gene_ids:
                if gid in expressed:
                    if gid not in gene_clusters:
                        gene_clusters[gid] = []
                    gene_clusters[gid].append({
                        "cluster_id": cluster["cluster_id"],
                        "mean_expression": expressed[gid],
                    })
        result["gene_expression_by_cluster"] = gene_clusters

    return result


def trajectory_regulation(db, species: str, gene_ids: list[str] | None = None) -> dict[str, Any]:
    if not _has_scrna_data(db, species):
        readiness = context.build_readiness_report(db, species, "expression", gene_ids[0] if gene_ids else None)
        return {
            "species": species,
            "supported": False,
            "reason": "No scRNA-seq data loaded for this species. Run: make scrna-data",
            "current_expression_readiness": readiness,
            "required_layers": ["scrna_datasets", "scrna_cluster_expression"],
            "requested_gene_ids": gene_ids or [],
        }

    clusters = _get_scrna_clusters(db, species)
    if len(clusters) < 2:
        return {
            "species": species,
            "supported": False,
            "reason": f"Need at least 2 clusters for trajectory analysis, found {len(clusters)}",
            "requested_gene_ids": gene_ids or [],
        }

    tf_profiles: dict[str, list[dict]] = {}
    cluster_order = [c["cluster_id"] for c in clusters]

    for cluster in clusters:
        expressed = _cluster_expressed_genes(db, species, cluster["cluster_id"])
        regulators = _score_tf_activity(db, species, expressed, top=50)

        for reg in regulators:
            tid = reg["gene_id"]
            if tid not in tf_profiles:
                tf_profiles[tid] = []
            tf_profiles[tid].append({
                "cluster_id": cluster["cluster_id"],
                "score": reg["score"],
                "tf_expr": reg["tf_mean_expr"],
                "overlap": reg["overlap"],
            })

    dynamic_tfs = []
    for tf_id, profile in tf_profiles.items():
        if len(profile) < 2:
            continue
        scores = [p["score"] for p in profile]
        max_score = max(scores)
        min_score = min(scores)
        score_range = max_score - min_score
        if score_range < 0.1:
            continue

        peak_cluster = profile[scores.index(max_score)]["cluster_id"]
        trough_cluster = profile[scores.index(min_score)]["cluster_id"]

        symbol = db.conn.execute(
            "SELECT symbol FROM genes WHERE id = ?", (tf_id,)
        ).fetchone()

        dynamic_tfs.append({
            "gene_id": tf_id,
            "symbol": symbol[0] if symbol else tf_id,
            "score_range": round(score_range, 4),
            "max_score": round(max_score, 4),
            "min_score": round(min_score, 4),
            "peak_cluster": peak_cluster,
            "trough_cluster": trough_cluster,
            "profile": profile,
        })

    dynamic_tfs.sort(key=lambda x: -x["score_range"])

    result = {
        "species": species,
        "supported": True,
        "analysis_type": "cluster_variation",
        "n_clusters": len(clusters),
        "cluster_order": cluster_order,
        "dynamic_regulators": dynamic_tfs[:25],
        "requested_gene_ids": gene_ids or [],
        "note": "This is cluster-level variation analysis, NOT pseudotime trajectory inference. "
                "Cluster order is arbitrary (database insertion order). TFs are ranked by activity "
                "score range across clusters, not by temporal dynamics. True trajectory analysis "
                "requires pseudotime inference (e.g. Monocle, PAGA) on the original count matrix.",
    }

    if gene_ids:
        gene_dynamics = {}
        for gid in gene_ids:
            profile = []
            for cluster in clusters:
                expressed = _cluster_expressed_genes(db, species, cluster["cluster_id"])
                profile.append({
                    "cluster_id": cluster["cluster_id"],
                    "expression": expressed.get(gid, 0.0),
                })
            gene_dynamics[gid] = profile
        result["gene_dynamics"] = gene_dynamics

    return result


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
