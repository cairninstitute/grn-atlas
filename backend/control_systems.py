"""Biological control-system discovery on top of signed feedback topology."""

from __future__ import annotations

import hashlib
import math
import sqlite3
from collections import Counter, defaultdict
from typing import Any, Iterable

import igraph as ig


RHYTHM_TERMS = ("circadian", "rhythm", "clock", "diurnal")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _chunks(values: Iterable[str], size: int = 800) -> Iterable[list[str]]:
    values = list(values)
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _hypergeom_tail(population: int, successes: int, draws: int, observed: int) -> float:
    """Exact upper-tail hypergeometric probability without scipy."""
    if not population or not successes or not draws or not observed:
        return 1.0
    denominator = math.comb(population, draws)
    upper = min(successes, draws)
    lower = max(observed, 0)
    return min(1.0, sum(
        math.comb(successes, hits) * math.comb(population - successes, draws - hits)
        for hits in range(lower, upper + 1)
        if 0 <= draws - hits <= population - successes
    ) / denominator)


def _annotation_candidates(
    conn: sqlite3.Connection,
    species: str,
    feedback_ids: set[str],
    population: int,
    max_system_genes: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    sources = (
        ("pathway", "pathway_annotations", "pathways", "pathway_id"),
        ("go", "go_annotations", "go_terms", "go_id"),
    )
    for source, annotation_table, term_table, key in sources:
        if not (_table_exists(conn, annotation_table) and _table_exists(conn, term_table)):
            continue
        anchors: dict[str, set[str]] = defaultdict(set)
        for chunk in _chunks(feedback_ids):
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(
                f"SELECT gene_id, {key} FROM {annotation_table} "
                f"WHERE gene_id IN ({placeholders})", chunk,
            ).fetchall()
            for gene_id, term_id in rows:
                anchors[term_id].add(gene_id)
        if not anchors:
            continue

        term_ids = list(anchors)
        metadata: dict[str, tuple[str, int]] = {}
        for chunk in _chunks(term_ids):
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(
                f"SELECT t.{key}, t.name, COUNT(DISTINCT a.gene_id) "
                f"FROM {term_table} t JOIN {annotation_table} a ON a.{key}=t.{key} "
                "JOIN genes g ON g.id=a.gene_id "
                f"WHERE g.species=? AND t.{key} IN ({placeholders}) "
                f"GROUP BY t.{key}, t.name",
                (species, *chunk),
            ).fetchall()
            metadata.update({row[0]: (row[1], int(row[2])) for row in rows})

        ranked = []
        for term_id, anchor_ids in anchors.items():
            name, total = metadata.get(term_id, (term_id, population))
            observed = len(anchor_ids)
            if observed < 2 or total < 2 or total > max_system_genes:
                continue
            fold = observed / max(len(feedback_ids), 1) / (total / max(population, 1))
            p_value = _hypergeom_tail(population, total, len(feedback_ids), observed)
            if source == "go" and fold < 1.5 and p_value > 0.05:
                continue
            ranked.append((p_value, -fold, -observed, term_id, name, total, anchor_ids))

        for p_value, negative_fold, _, term_id, name, total, anchor_ids in sorted(ranked)[:30]:
            rows = conn.execute(
                f"SELECT a.gene_id FROM {annotation_table} a JOIN genes g ON g.id=a.gene_id "
                f"WHERE a.{key}=? AND g.species=? ORDER BY a.gene_id",
                (term_id, species),
            ).fetchall()
            candidates.append({
                "source": source,
                "term_id": term_id,
                "name": name,
                "member_ids": {row[0] for row in rows},
                "anchor_ids": set(anchor_ids),
                "term_gene_count": total,
                "enrichment": {
                    "feedback_genes": len(anchor_ids),
                    "fold": round(-negative_fold, 3),
                    "p_value": float(f"{p_value:.4g}"),
                },
            })
    return candidates


def _de_novo_candidates(circuits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group representative circuits that overlap in at least one gene."""
    if not circuits:
        return []
    parent = list(range(len(circuits)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    by_gene: dict[str, list[int]] = defaultdict(list)
    for index, circuit in enumerate(circuits):
        for gene in circuit["genes"]:
            by_gene[gene["id"]].append(index)
    for indices in by_gene.values():
        for index in indices[1:]:
            union(indices[0], index)

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, circuit in enumerate(circuits):
        groups[find(index)].append(circuit)
    candidates = []
    for group in groups.values():
        member_ids = {gene["id"] for circuit in group for gene in circuit["genes"]}
        symbols = sorted({gene["symbol"] for circuit in group for gene in circuit["genes"]})
        candidates.append({
            "source": "de_novo",
            "term_id": None,
            "name": " / ".join(symbols[:3]) + (" feedback module" if len(symbols) <= 3 else " control module"),
            "member_ids": member_ids,
            "anchor_ids": member_ids,
            "enrichment": None,
            "circuits": group,
        })
    return candidates


def _subgraph_edges(
    graph: ig.Graph, member_ids: set[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    indices = [vertex.index for vertex in graph.vs if vertex["gene_id"] in member_ids]
    index_set = set(indices)
    involved: set[str] = set()
    edges = []
    for edge in graph.es:
        if edge.source not in index_set or edge.target not in index_set:
            continue
        source = graph.vs[edge.source]["gene_id"]
        target = graph.vs[edge.target]["gene_id"]
        involved.update((source, target))
        edges.append({
            "source": source,
            "target": target,
            "sign": "repression" if edge["repression"] else "activation",
            "regulation_type": "repression" if edge["repression"] else "activation",
            "confidence": round(float(edge["confidence"]), 4),
            "sign_evidence": "measured" if edge["measured"] else "perturbation",
        })
    return sorted(involved), edges


def _edge_context(
    conn: sqlite3.Connection,
    species: str,
    gene_ids: set[str],
    edge_pairs: set[tuple[str, str]],
) -> dict[str, Any]:
    if not edge_pairs:
        return {
            "cis_supported_edges": 0,
            "perturbation_supported_edges": 0,
            "coexpressed_edges": 0,
            "top_tissues": [],
        }
    cis_pairs: set[tuple[str, str]] = set()
    perturbation_pairs: set[tuple[str, str]] = set()
    coexpressed_pairs: set[tuple[str, str]] = set()
    tissue_values: dict[str, list[float]] = defaultdict(list)
    for chunk in _chunks(gene_ids):
        placeholders = ",".join("?" for _ in chunk)
        if _table_exists(conn, "cis_support_edges"):
            rows = conn.execute(
                f"SELECT source_id,target_id FROM cis_support_edges WHERE species=? "
                f"AND source_id IN ({placeholders})", (species, *chunk),
            ).fetchall()
            cis_pairs.update((row[0], row[1]) for row in rows if (row[0], row[1]) in edge_pairs)
        if _table_exists(conn, "perturbation_observations"):
            rows = conn.execute(
                f"SELECT perturbed_gene,affected_gene FROM perturbation_observations "
                f"WHERE species=? AND observed_significant=1 AND perturbed_gene IN ({placeholders})",
                (species, *chunk),
            ).fetchall()
            perturbation_pairs.update(
                (row[0], row[1]) for row in rows if (row[0], row[1]) in edge_pairs
            )
        if _table_exists(conn, "edge_tissue_weights"):
            rows = conn.execute(
                f"SELECT source_id,target_id,tissue,coexpression FROM edge_tissue_weights "
                f"WHERE species=? AND source_id IN ({placeholders})", (species, *chunk),
            ).fetchall()
            for source, target, tissue, value in rows:
                if (source, target) in edge_pairs and tissue != "_global" and abs(float(value)) >= 0.3:
                    tissue_values[tissue].append(abs(float(value)))
                    coexpressed_pairs.add((source, target))
    ranked_tissues = sorted(
        (
            {"tissue": tissue, "supported_edges": len(values), "mean_abs_coexpression": round(sum(values) / len(values), 3)}
            for tissue, values in tissue_values.items()
        ),
        key=lambda row: (-row["supported_edges"], -row["mean_abs_coexpression"], row["tissue"]),
    )[:5]
    return {
        "cis_supported_edges": len(cis_pairs),
        "perturbation_supported_edges": len(perturbation_pairs),
        "coexpressed_edges": len(coexpressed_pairs),
        "top_tissues": ranked_tissues,
    }


def _conservation_support(
    conn: sqlite3.Connection,
    gene_ids: set[str],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    if not edges or not _table_exists(conn, "orthologs"):
        return {"conserved_signed_edges": 0, "tested_edges": 0, "species": []}
    orthologs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for chunk in _chunks(gene_ids):
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT gene_a,gene_b,species_a,species_b FROM orthologs "
            f"WHERE gene_a IN ({placeholders}) OR gene_b IN ({placeholders})",
            (*chunk, *chunk),
        ).fetchall()
        for gene_a, gene_b, species_a, species_b in rows:
            if gene_a in gene_ids:
                orthologs[gene_a].append((gene_b, species_b))
            if gene_b in gene_ids:
                orthologs[gene_b].append((gene_a, species_a))

    candidate_pairs: dict[
        tuple[str, str], list[tuple[str, str, tuple[str, str]]]
    ] = defaultdict(list)
    tested_edges = 0
    for edge in edges:
        source_orthologs = orthologs.get(edge["source"], [])
        target_by_species: dict[str, list[str]] = defaultdict(list)
        for target_id, target_species in orthologs.get(edge["target"], []):
            target_by_species[target_species].append(target_id)
        edge_tested = False
        for source_id, source_species in source_orthologs:
            for target_id in target_by_species.get(source_species, []):
                candidate_pairs[(source_id, target_id)].append(
                    (edge["sign"], source_species, (edge["source"], edge["target"]))
                )
                edge_tested = True
        tested_edges += edge_tested
    if not candidate_pairs:
        return {"conserved_signed_edges": 0, "tested_edges": tested_edges, "species": []}

    observed: dict[tuple[str, str], str] = {}
    for chunk in _chunks({pair[0] for pair in candidate_pairs}):
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT source_id,target_id,sign FROM interactions WHERE source_id IN ({placeholders}) "
            "AND sign IN ('activation','repression')",
            chunk,
        ).fetchall()
        for source, target, sign in rows:
            if (source, target) in candidate_pairs:
                observed[(source, target)] = sign
    conserved_species = set()
    conserved_edges = set()
    for pair, observed_sign in observed.items():
        for expected_sign, target_species, original_edge in candidate_pairs[pair]:
            if observed_sign == expected_sign:
                conserved_species.add(target_species)
                conserved_edges.add(original_edge)
    return {
        "conserved_signed_edges": len(conserved_edges),
        "tested_edges": tested_edges,
        "species": sorted(conserved_species),
    }


def _classify(name: str, circuits: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    families = Counter(circuit["family"] for circuit in circuits)
    polarities = Counter(circuit["polarity"] for circuit in circuits)
    normalized_name = name.lower()
    reasons = []
    if any(term in normalized_name for term in RHYTHM_TERMS) and polarities["negative"]:
        reasons.extend(["rhythm-related biological annotation", "signed negative feedback present"])
        if families["repressilator"]:
            reasons.append("three-node repression cycle present")
            return "oscillator_candidate", "Oscillator candidate", reasons
        return "oscillator_scaffold", "Incomplete oscillator scaffold", reasons
    if families["repressilator"]:
        return "oscillator_candidate", "Oscillator candidate", ["three-node repression cycle present"]
    if families["mutual_repression"]:
        return "toggle_switch", "Toggle-switch candidate", ["mutual repression present"]
    if polarities["positive"] and polarities["negative"]:
        return "mixed_feedback", "Mixed feedback controller", ["positive and negative feedback coexist"]
    if polarities["positive"]:
        return "reinforcing_switch", "Reinforcing switch or memory candidate", ["positive feedback present"]
    return "negative_feedback", "Homeostatic or adaptive controller candidate", ["negative feedback present"]


def _build_system(
    conn: sqlite3.Connection,
    species: str,
    graph: ig.Graph,
    genes: dict[str, dict[str, Any]],
    candidate: dict[str, Any],
    all_circuits: list[dict[str, Any]],
) -> dict[str, Any] | None:
    seed_ids = set(candidate["member_ids"])
    anchor_ids = set(candidate["anchor_ids"])
    circuits = candidate.get("circuits") or []
    if not circuits:
        for circuit in all_circuits:
            circuit_ids = {gene["id"] for gene in circuit["genes"]}
            overlap = len(circuit_ids & seed_ids) / len(circuit_ids)
            if circuit_ids <= seed_ids or (circuit_ids & anchor_ids and overlap >= 0.5):
                circuits.append(circuit)
    expanded_ids = seed_ids | {
        gene["id"] for circuit in circuits for gene in circuit["genes"]
    }
    involved_ids, edges = _subgraph_edges(graph, expanded_ids)
    member_ids = set(involved_ids) | anchor_ids
    if not circuits or len(member_ids) < 2:
        return None
    edge_pairs = {(edge["source"], edge["target"]) for edge in edges}
    context = _edge_context(conn, species, member_ids, edge_pairs)
    context["conservation"] = _conservation_support(conn, member_ids, edges)
    architecture, architecture_label, reasons = _classify(candidate["name"], circuits)
    strongest_circuit = max(circuit["score"] for circuit in circuits)
    context_fraction = min(1.0, (
        context["cis_supported_edges"] + context["perturbation_supported_edges"] +
        context["coexpressed_edges"] + context["conservation"]["conserved_signed_edges"]
    ) / max(4 * len(edges), 1))
    enrichment = candidate.get("enrichment")
    annotation_strength = 0.0
    if enrichment:
        annotation_strength = min(1.0, math.log1p(enrichment["fold"]) / math.log(6))
    evidence_strength = sum(edge["confidence"] for edge in edges) / max(len(edges), 1)
    score = 0.38 * strongest_circuit + 0.24 * annotation_strength + 0.23 * evidence_strength + 0.15 * context_fraction
    completeness = "closed_signed_feedback"
    if architecture == "oscillator_scaffold":
        completeness = "partial_architecture"
    system_id = hashlib.sha256(
        f"{species}|{candidate['source']}|{candidate.get('term_id')}|{'|'.join(sorted(member_ids))}".encode()
    ).hexdigest()[:20]
    sorted_genes = sorted(
        (genes[gene_id] for gene_id in member_ids if gene_id in genes),
        key=lambda gene: (gene["symbol"], gene["id"]),
    )
    return {
        "system_id": system_id,
        "name": candidate["name"],
        "discovery_mode": "annotation_supported" if candidate["source"] != "de_novo" else "de_novo_topology",
        "annotation": {
            "source": candidate["source"],
            "term_id": candidate.get("term_id"),
            "enrichment": enrichment,
        },
        "architecture": architecture,
        "architecture_label": architecture_label,
        "classification_reasons": reasons,
        "completeness": completeness,
        "score": round(min(1.0, score), 4),
        "confidence_label": "high" if score >= 0.8 else "supported" if score >= 0.6 else "candidate",
        "gene_count": len(sorted_genes),
        "edge_count": len(edges),
        "feedback_gene_count": len({gene["id"] for circuit in circuits for gene in circuit["genes"]}),
        "genes": sorted_genes,
        "edges": edges,
        "circuits": sorted(circuits, key=lambda circuit: (-circuit["score"], circuit["length"]))[:8],
        "context_support": context,
        "evidence_boundary": (
            "Architecture is classified from signed topology and biological context. "
            "It is a mechanistic hypothesis, not proof of system dynamics."
        ),
    }


def discover_control_systems(
    conn: sqlite3.Connection,
    species: str,
    graph: ig.Graph,
    genes: dict[str, dict[str, Any]],
    cores: list[dict[str, Any]],
    max_systems: int = 20,
    max_system_genes: int = 80,
) -> list[dict[str, Any]]:
    """Discover interpretable biological systems containing signed feedback."""
    feedback_ids = {gene_id for core in cores for gene_id in core.get("_gene_ids", [])}
    all_circuits = [circuit for core in cores for circuit in core["circuits"]]
    if not feedback_ids or not all_circuits:
        return []
    candidates = _annotation_candidates(
        conn, species, feedback_ids, len(genes), max_system_genes,
    )
    candidates.extend(_de_novo_candidates(all_circuits))
    systems = []
    for candidate in candidates:
        system = _build_system(conn, species, graph, genes, candidate, all_circuits)
        if system is not None:
            systems.append(system)

    systems.sort(key=lambda system: (
        system["discovery_mode"] != "annotation_supported",
        -system["score"],
        system["gene_count"],
        system["name"],
    ))
    retained = []
    for system in systems:
        ids = {gene["id"] for gene in system["genes"]}
        duplicate = False
        for existing in retained:
            existing_ids = {gene["id"] for gene in existing["genes"]}
            overlap = len(ids & existing_ids) / max(min(len(ids), len(existing_ids)), 1)
            if overlap >= 0.85 and system["architecture"] == existing["architecture"]:
                duplicate = True
                break
        if not duplicate:
            retained.append(system)
        if len(retained) >= max_systems:
            break
    for rank, system in enumerate(retained, start=1):
        system["rank"] = rank
    return retained
