"""Bounded feedback-circuit discovery and control analysis for signed GRNs."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import igraph as ig
import networkx as nx

import control_systems


ALGORITHM_VERSION = "feedback-control-v3"
STRONG_SIGN_EVIDENCE = ("measured", "perturbation")


@dataclass(frozen=True)
class FeedbackParameters:
    min_confidence: float = 0.5
    evidence_tiers: tuple[str, ...] = STRONG_SIGN_EVIDENCE
    max_loop_length: int = 6
    max_cores: int = 50
    max_circuits: int = 100
    circuits_per_core: int = 12
    max_search_states: int = 100_000
    exact_controller_max_nodes: int = 18
    max_controllers: int = 30
    max_systems: int = 20
    max_system_genes: int = 80
    discover_systems: bool = True
    exact_cycle_max_nodes: int = 10
    exact_cycle_max_edges: int = 30
    exact_cycle_limit: int = 50_000
    cycle_cover_max_edges: int = 1_000
    max_bridge_hops: int = 3

    def normalized(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_tiers"] = sorted(set(self.evidence_tiers))
        return data


def _json_list(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _canonical_cycle(nodes: list[str]) -> tuple[str, ...]:
    if len(nodes) == 1:
        return (nodes[0],)
    rotations = [tuple(nodes[index:] + nodes[:index]) for index in range(len(nodes))]
    return min(rotations)


def _edge_product(edges: list[dict[str, Any]]) -> int:
    product = 1
    for edge in edges:
        product *= -1 if edge["sign"] == "repression" else 1
    return product


def _circuit_family(nodes: list[str], edges: list[dict[str, Any]]) -> tuple[str, str, str]:
    product = _edge_product(edges)
    polarity = "positive" if product > 0 else "negative"
    signs = [edge["sign"] for edge in edges]
    if len(nodes) == 1:
        if polarity == "positive":
            return "positive_autoregulation", polarity, "state reinforcement or thresholding candidate"
        return "negative_autoregulation", polarity, "response acceleration or noise-damping candidate"
    if len(nodes) == 2 and signs.count("repression") == 2:
        return "mutual_repression", polarity, "toggle-switch or state-memory candidate"
    if len(nodes) == 2 and signs.count("activation") == 2:
        return "mutual_activation", polarity, "state reinforcement or memory candidate"
    if len(nodes) == 3 and signs.count("repression") == 3:
        return "repressilator", polarity, "oscillation candidate if delays and kinetics support it"
    if polarity == "positive":
        return "positive_feedback", polarity, "switch, amplification, or memory candidate"
    return "negative_feedback", polarity, "homeostasis, adaptation, or oscillation candidate"


def _circuit_score(edges: list[dict[str, Any]]) -> tuple[float, str, dict[str, float]]:
    confidences = [float(edge["confidence"]) for edge in edges]
    weakest = min(confidences)
    geometric = math.exp(sum(math.log(max(value, 1e-9)) for value in confidences) / len(confidences))
    evidence_values = [1.0 if edge["sign_evidence"] == "measured" else 0.82 for edge in edges]
    evidence = min(evidence_values)
    independent_sources = min(1.0, sum(min(len(edge["sources"]), 3) / 3 for edge in edges) / len(edges))
    score = 0.50 * weakest + 0.25 * geometric + 0.20 * evidence + 0.05 * independent_sources
    if all(edge["sign_evidence"] == "measured" for edge in edges) and weakest >= 0.7:
        label = "high"
    elif weakest >= 0.5 and all(edge["sign_evidence"] in STRONG_SIGN_EVIDENCE for edge in edges):
        label = "supported"
    else:
        label = "structural_candidate"
    return round(score, 4), label, {
        "weakest_edge": round(weakest, 4),
        "geometric_mean": round(geometric, 4),
        "evidence_floor": round(evidence, 4),
        "source_support": round(independent_sources, 4),
    }


def _edge_record(graph: ig.Graph, source: int, target: int) -> dict[str, Any]:
    edge_id = graph.get_eid(source, target, directed=True, error=False)
    if edge_id < 0:
        raise KeyError(f"missing cycle edge {source}->{target}")
    return {
        "source": graph.vs[source]["gene_id"],
        "target": graph.vs[target]["gene_id"],
        "sign": "repression" if graph.es[edge_id]["repression"] else "activation",
        "regulation_type": "repression" if graph.es[edge_id]["repression"] else "activation",
        "sign_evidence": "measured" if graph.es[edge_id]["measured"] else "perturbation",
        "confidence": round(float(graph.es[edge_id]["confidence"]), 4),
        "sources": [],
        "pmids": [],
    }


def _cycle_record(
    graph: ig.Graph,
    vertices: list[int],
    genes: dict[str, dict[str, Any]],
    core_id: str,
) -> dict[str, Any]:
    node_ids = [graph.vs[index]["gene_id"] for index in vertices]
    pairs = [(vertices[index], vertices[(index + 1) % len(vertices)]) for index in range(len(vertices))]
    edges = [_edge_record(graph, source, target) for source, target in pairs]
    family, polarity, behavior = _circuit_family(node_ids, edges)
    score, confidence_label, score_components = _circuit_score(edges)
    canonical = _canonical_cycle(node_ids)
    circuit_id = hashlib.sha256(
        f"{core_id}|{'|'.join(canonical)}".encode("utf-8")
    ).hexdigest()[:20]
    return {
        "circuit_id": circuit_id,
        "core_id": core_id,
        "family": family,
        "polarity": polarity,
        "behavior_hypothesis": behavior,
        "length": len(node_ids),
        "score": score,
        "confidence_label": confidence_label,
        "score_components": score_components,
        "genes": [genes[gene_id] for gene_id in node_ids],
        "edges": edges,
    }


def _representative_cycles(
    graph: ig.Graph,
    genes: dict[str, dict[str, Any]],
    core_id: str,
    params: FeedbackParameters,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    node_ids = graph.vs["gene_id"]
    adjacency: dict[int, list[int]] = {}

    def outgoing(source: int) -> list[int]:
        if source not in adjacency:
            targets = [target for target in graph.neighbors(source, mode="out") if target != source]
            targets.sort(key=lambda target: (
                -float(graph.es[graph.get_eid(source, target)]["confidence"]),
                graph.vs[target]["gene_id"],
            ))
            adjacency[source] = targets
        return adjacency[source]

    records: dict[tuple[str, ...], dict[str, Any]] = {}
    for source, gene_id in enumerate(node_ids):
        if graph.get_eid(source, source, directed=True, error=False) >= 0:
            records[(gene_id,)] = _cycle_record(graph, [source], genes, core_id)
    for source in range(graph.vcount()):
        for target in outgoing(source):
            source_id, target_id = node_ids[source], node_ids[target]
            if source_id < target_id and graph.get_eid(target, source, directed=True, error=False) >= 0:
                key = _canonical_cycle([source_id, target_id])
                records[key] = _cycle_record(graph, [source, target], genes, core_id)

    state_count = 0
    state_budget_hit = False
    candidate_cap = max(params.circuits_per_core * 20, params.circuits_per_core)
    starts = sorted(range(graph.vcount()), key=lambda index: (-graph.degree(index, mode="out"), node_ids[index]))
    for start in starts:
        if len(records) >= candidate_cap:
            break
        queue = deque([(start, [start])])
        while queue and len(records) < candidate_cap:
            current, path = queue.popleft()
            for target in outgoing(current):
                state_count += 1
                if state_count > params.max_search_states:
                    state_budget_hit = True
                    break
                if target == start:
                    if len(path) >= 3:
                        path_ids = [node_ids[index] for index in path]
                        key = _canonical_cycle(path_ids)
                        if key not in records:
                            records[key] = _cycle_record(graph, path, genes, core_id)
                    continue
                if len(path) >= params.max_loop_length or target in path:
                    continue
                queue.append((target, path + [target]))
            if state_budget_hit:
                break
        if state_budget_hit:
            break

    ranked = sorted(
        records.values(),
        key=lambda circuit: (-circuit["score"], circuit["length"], circuit["circuit_id"]),
    )
    selected = ranked[:params.circuits_per_core]
    return selected, {
        "search_states": state_count,
        "candidate_circuits": len(records),
        "returned_circuits": len(selected),
        "state_budget_hit": state_budget_hit,
        "candidate_cap_hit": len(records) >= candidate_cap,
        "truncated": state_budget_hit or len(ranked) > len(selected) or len(records) >= candidate_cap,
    }


def _backbone_edges(graph: ig.Graph) -> list[dict[str, Any]]:
    """Return every edge in a cyclic SCC; each is cycle-capable by definition."""
    return [
        _edge_record(graph, edge.source, edge.target)
        for edge in graph.es
    ]


def _exact_cycle_catalog(
    graph: ig.Graph,
    genes: dict[str, dict[str, Any]],
    core_id: str,
    params: FeedbackParameters,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Enumerate all simple directed cycles only while the core remains tractable."""
    eligible = (
        graph.vcount() <= params.exact_cycle_max_nodes
        and graph.ecount() <= params.exact_cycle_max_edges
    )
    if not eligible:
        return [], {
            "mode": "on_demand",
            "exact": False,
            "cataloged_cycles": 0,
            "reason": "core exceeds exact-catalog size thresholds",
        }

    directed = nx.DiGraph()
    node_ids = list(graph.vs["gene_id"])
    directed.add_nodes_from(sorted(node_ids))
    directed.add_edges_from(sorted(
        (node_ids[edge.source], node_ids[edge.target]) for edge in graph.es
    ))
    index = {gene_id: position for position, gene_id in enumerate(node_ids)}
    records: list[dict[str, Any]] = []
    exhausted = True
    for cycle in nx.simple_cycles(directed):
        if len(records) >= params.exact_cycle_limit:
            exhausted = False
            break
        records.append(_cycle_record(
            graph, [index[gene_id] for gene_id in cycle], genes, core_id,
        ))
    records.sort(key=lambda row: (row["length"], row["circuit_id"]))
    return records, {
        "mode": "exact" if exhausted else "bounded_catalog",
        "exact": exhausted,
        "cataloged_cycles": len(records),
        "reason": None if exhausted else "exact cycle limit reached",
    }


def _compact_cycle_cover(
    graph: ig.Graph,
    genes: dict[str, dict[str, Any]],
    core_id: str,
    params: FeedbackParameters,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build short directed witness cycles that cover internal feedback edges."""
    if graph.ecount() > params.cycle_cover_max_edges:
        return [], {
            "complete": False,
            "covered_edges": 0,
            "total_edges": graph.ecount(),
            "coverage": 0.0,
            "reason": "core exceeds cycle-cover edge threshold",
        }

    node_ids = list(graph.vs["gene_id"])
    index = {gene_id: position for position, gene_id in enumerate(node_ids)}
    directed = nx.DiGraph()
    directed.add_nodes_from(node_ids)
    directed.add_edges_from(
        (node_ids[edge.source], node_ids[edge.target]) for edge in graph.es
    )
    candidates: dict[tuple[str, ...], tuple[dict[str, Any], set[tuple[str, str]]]] = {}
    for source, target in sorted(directed.edges()):
        if source == target:
            cycle = [source]
        else:
            try:
                cycle = [source] + nx.shortest_path(directed, target, source)[:-1]
            except nx.NetworkXNoPath:
                continue
        key = _canonical_cycle(cycle)
        if key in candidates:
            continue
        record = _cycle_record(graph, [index[gene_id] for gene_id in cycle], genes, core_id)
        covered = {
            (cycle[position], cycle[(position + 1) % len(cycle)])
            for position in range(len(cycle))
        }
        candidates[key] = (record, covered)

    uncovered = set(directed.edges())
    selected: list[dict[str, Any]] = []
    remaining = dict(candidates)
    while uncovered and remaining:
        key, (record, covered) = max(
            remaining.items(),
            key=lambda item: (
                len(item[1][1] & uncovered),
                -item[1][0]["length"],
                item[1][0]["score"],
                item[0],
            ),
        )
        gain = covered & uncovered
        del remaining[key]
        if not gain:
            continue
        selected.append(record)
        uncovered -= gain
    covered_count = directed.number_of_edges() - len(uncovered)
    return selected, {
        "complete": not uncovered,
        "covered_edges": covered_count,
        "total_edges": directed.number_of_edges(),
        "coverage": round(covered_count / max(directed.number_of_edges(), 1), 4),
        "reason": None if not uncovered else "not every edge received a witness cycle",
    }


def _cyclic_components(graph: ig.Graph) -> list[list[int]]:
    components = []
    for component in graph.connected_components(mode="strong"):
        vertices = list(component)
        if len(vertices) > 1:
            components.append(vertices)
        elif graph.are_adjacent(vertices[0], vertices[0]):
            components.append(vertices)
    return components


def _controller_set(
    graph: ig.Graph,
    genes: dict[str, dict[str, Any]],
    cycle_counts: Counter[str],
    params: FeedbackParameters,
) -> dict[str, Any]:
    exact_allowed = graph.vcount() <= params.exact_controller_max_nodes and graph.ecount() <= 80
    if exact_allowed:
        indices = graph.feedback_vertex_set(method="ip")
        controller_ids = [graph.vs[index]["gene_id"] for index in indices]
        method = "exact_minimum_feedback_vertex_set"
        complete = True
    else:
        work = graph.copy()
        controller_ids = []
        while len(controller_ids) < params.max_controllers:
            cyclic = _cyclic_components(work)
            if not cyclic:
                break
            candidates = set(index for component in cyclic for index in component)
            degrees = []
            for index in candidates:
                indegree = work.degree(index, mode="in", loops=True)
                outdegree = work.degree(index, mode="out", loops=True)
                gene_id = work.vs[index]["gene_id"]
                degrees.append((indegree * outdegree, indegree + outdegree,
                                cycle_counts.get(gene_id, 0), gene_id, index))
            _, _, _, gene_id, selected = max(degrees)
            controller_ids.append(gene_id)
            work.delete_vertices([selected])
        complete = not _cyclic_components(work)
        method = "bounded_greedy_feedback_vertex_set"

    ranked = sorted(
        controller_ids,
        key=lambda gene_id: (-cycle_counts.get(gene_id, 0), gene_id),
    )
    return {
        "method": method,
        "exact": method.startswith("exact"),
        "breaks_all_detected_feedback": complete,
        "truncated": not complete,
        "controllers": [
            {
                **genes[gene_id],
                "representative_circuit_count": cycle_counts.get(gene_id, 0),
            }
            for gene_id in ranked
        ],
        "caveat": (
            "A feedback vertex set identifies structural intervention points; it does not determine "
            "perturbation direction or guarantee control of a biological attractor."
        ),
    }


def _load_signed_graph(
    conn: sqlite3.Connection,
    species: str,
    params: FeedbackParameters,
) -> tuple[ig.Graph, dict[str, dict[str, Any]], str]:
    gene_rows = conn.execute(
        "SELECT id, symbol, name, is_tf FROM genes WHERE species = ? ORDER BY id",
        (species,),
    ).fetchall()
    genes = {
        row[0]: {
            "id": row[0], "symbol": row[1], "name": row[2], "is_tf": bool(row[3]),
            "species": species,
        }
        for row in gene_rows
    }
    ids = list(genes)
    index = {gene_id: position for position, gene_id in enumerate(ids)}
    graph = ig.Graph(n=len(ids), directed=True)
    graph.vs["gene_id"] = ids
    digest = hashlib.sha256()
    for gene_id in ids:
        digest.update(f"gene\0{gene_id}\n".encode("utf-8"))
    placeholders = ",".join("?" for _ in params.evidence_tiers)
    cursor = conn.execute(
        f"""
        SELECT i.source_id, i.target_id, i.sign, i.sign_evidence, i.confidence
        FROM interactions i
        JOIN genes s ON s.id = i.source_id
        JOIN genes t ON t.id = i.target_id
        WHERE s.species = ? AND t.species = ?
          AND i.sign IN ('activation', 'repression')
          AND i.sign_evidence IN ({placeholders})
          AND i.confidence >= ?
        ORDER BY i.source_id, i.target_id
        """,
        (species, species, *params.evidence_tiers, params.min_confidence),
    )
    while True:
        rows = cursor.fetchmany(100_000)
        if not rows:
            break
        edges = [(index[row[0]], index[row[1]]) for row in rows]
        graph.add_edges(edges, attributes={
            "confidence": [float(row[4]) for row in rows],
            "repression": [row[2] == "repression" for row in rows],
            "measured": [row[3] == "measured" for row in rows],
        })
        for row in rows:
            digest.update(
                f"{row[0]}\0{row[1]}\0{row[2]}\0{row[3]}\0{float(row[4]):.8f}\n".encode("utf-8")
            )
    return graph, genes, digest.hexdigest()


def _discover_core_relationships(
    graph: ig.Graph,
    genes: dict[str, dict[str, Any]],
    cores: list[dict[str, Any]],
    max_hops: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Connect feedback cores through short signed paths containing only acyclic bridges."""
    if len(cores) < 2:
        return [], []
    gene_to_vertex = {
        gene_id: index for index, gene_id in enumerate(graph.vs["gene_id"])
    }
    vertex_to_core: dict[int, str] = {}
    core_by_id = {core["core_id"]: core for core in cores}
    for core in cores:
        for gene_id in core.get("_gene_ids", []):
            vertex_to_core[gene_to_vertex[gene_id]] = core["core_id"]

    adjacency = {
        vertex: sorted(
            graph.neighbors(vertex, mode="out"),
            key=lambda target: graph.vs[target]["gene_id"],
        )
        for vertex in range(graph.vcount())
        if graph.degree(vertex, mode="out")
    }
    best_paths: dict[tuple[str, str], list[int]] = {}
    for source_core in cores:
        source_id = source_core["core_id"]
        starts = sorted(
            (gene_to_vertex[gene_id] for gene_id in source_core.get("_gene_ids", [])),
            key=lambda vertex: graph.vs[vertex]["gene_id"],
        )
        queue = deque((vertex, [vertex]) for vertex in starts)
        visited_depth = {vertex: 0 for vertex in starts}
        while queue:
            current, path = queue.popleft()
            depth = len(path) - 1
            if depth >= max_hops:
                continue
            for target in adjacency.get(current, []):
                target_core = vertex_to_core.get(target)
                if target_core == source_id:
                    continue
                next_path = path + [target]
                if target_core is not None:
                    key = (source_id, target_core)
                    existing = best_paths.get(key)
                    path_key = tuple(graph.vs[index]["gene_id"] for index in next_path)
                    existing_key = tuple(
                        graph.vs[index]["gene_id"] for index in existing
                    ) if existing else None
                    if existing is None or len(next_path) < len(existing) or (
                        len(next_path) == len(existing) and path_key < existing_key
                    ):
                        best_paths[key] = next_path
                    continue
                next_depth = depth + 1
                if next_depth < visited_depth.get(target, max_hops + 1):
                    visited_depth[target] = next_depth
                    queue.append((target, next_path))

    relationships = []
    for (source_core_id, target_core_id), path in sorted(best_paths.items()):
        edges = [
            _edge_record(graph, path[index], path[index + 1])
            for index in range(len(path) - 1)
        ]
        hop_count = len(edges)
        weakest = min(float(edge["confidence"]) for edge in edges)
        score = weakest * (1.0 if hop_count == 1 else 0.84 if hop_count == 2 else 0.70)
        net_sign = "activation" if _edge_product(edges) > 0 else "repression"
        path_ids = [graph.vs[index]["gene_id"] for index in path]
        relationship_id = hashlib.sha256(
            f"{source_core_id}|{target_core_id}|{'|'.join(path_ids)}".encode("utf-8")
        ).hexdigest()[:20]
        relationships.append({
            "relationship_id": relationship_id,
            "source_core_id": source_core_id,
            "target_core_id": target_core_id,
            "source_core_rank": core_by_id[source_core_id]["rank"],
            "target_core_rank": core_by_id[target_core_id]["rank"],
            "relationship_type": "direct_regulation" if hop_count == 1 else "bridged_regulatory_path",
            "hop_count": hop_count,
            "score": round(score, 4),
            "net_sign": net_sign,
            "path_genes": [genes[gene_id] for gene_id in path_ids],
            "bridge_genes": [genes[gene_id] for gene_id in path_ids[1:-1]],
            "edges": edges,
        })

    undirected = nx.Graph()
    undirected.add_nodes_from(core_by_id)
    undirected.add_edges_from(
        (row["source_core_id"], row["target_core_id"]) for row in relationships
    )
    groups = []
    for component in nx.connected_components(undirected):
        if len(component) < 2:
            continue
        core_ids = sorted(component, key=lambda core_id: core_by_id[core_id]["rank"])
        group_relationships = [
            row for row in relationships
            if row["source_core_id"] in component and row["target_core_id"] in component
        ]
        group_id = hashlib.sha256(
            f"core-group|{'|'.join(sorted(core_ids))}".encode("utf-8")
        ).hexdigest()[:20]
        groups.append({
            "group_id": group_id,
            "rank": 0,
            "core_ids": core_ids,
            "core_count": len(core_ids),
            "relationship_count": len(group_relationships),
            "gene_count": sum(core_by_id[core_id]["node_count"] for core_id in core_ids),
            "bridge_gene_count": len({
                gene["id"] for row in group_relationships for gene in row["bridge_genes"]
            }),
            "score": round(sum(row["score"] for row in group_relationships) / len(group_relationships), 4),
            "cores": [
                {
                    "core_id": core_id,
                    "rank": core_by_id[core_id]["rank"],
                    "score": core_by_id[core_id]["score"],
                    "node_count": core_by_id[core_id]["node_count"],
                    "edge_count": core_by_id[core_id]["edge_count"],
                    "top_genes": core_by_id[core_id]["gene_sample"][:5],
                }
                for core_id in core_ids
            ],
            "relationship_ids": [row["relationship_id"] for row in group_relationships],
        })
    groups.sort(key=lambda group: (-group["score"], -group["core_count"], group["group_id"]))
    for rank, group in enumerate(groups, start=1):
        group["rank"] = rank
    return relationships, groups


def _hydrate_circuit_provenance(
    conn: sqlite3.Connection,
    circuits: Iterable[dict[str, Any]],
) -> None:
    for circuit in circuits:
        _hydrate_edge_provenance(conn, circuit["edges"])
        score, label, components = _circuit_score(circuit["edges"])
        circuit["score"] = score
        circuit["confidence_label"] = label
        circuit["score_components"] = components


def _hydrate_edge_provenance(
    conn: sqlite3.Connection, edges: Iterable[dict[str, Any]],
) -> None:
    for edge in edges:
        row = conn.execute(
            "SELECT sources, pmids FROM interactions WHERE source_id = ? AND target_id = ?",
            (edge["source"], edge["target"]),
        ).fetchone()
        if row:
            edge["sources"] = _json_list(row[0])
            edge["pmids"] = _json_list(row[1])


def analyze_feedback(
    conn: sqlite3.Connection,
    species: str,
    params: FeedbackParameters | None = None,
) -> dict[str, Any]:
    """Analyze bounded representative feedback circuits in one species GRN."""
    params = params or FeedbackParameters()
    graph, genes, graph_hash = _load_signed_graph(conn, species, params)
    parameter_json = json.dumps(params.normalized(), sort_keys=True, separators=(",", ":"))
    run_id = hashlib.sha256(
        f"{ALGORITHM_VERSION}|{species}|{graph_hash}|{parameter_json}".encode("utf-8")
    ).hexdigest()[:24]
    if graph.ecount() == 0:
        return {
            "run_id": run_id,
            "algorithm_version": ALGORITHM_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "species": species,
            "parameters": params.normalized(),
            "graph": {
                "nodes": graph.vcount(), "edges": 0, "graph_hash": graph_hash,
                "signed_evidence_only": True,
            },
            "summary": {
                "feedback_cores": 0, "feedback_cores_returned": 0,
                "feedback_genes": 0, "feedback_genes_returned": 0,
                "feedback_edges": 0, "feedback_edges_returned": 0,
                "exact_cycle_catalogs": 0, "cataloged_cycles": 0,
                "circuits_returned": 0, "controller_candidates": 0,
                "biological_systems": 0, "core_relationships": 0, "core_groups": 0,
            },
            "cores": [],
            "systems": [],
            "core_relationships": [],
            "core_groups": [],
            "truncation": {"cores": False, "circuits": False, "search": False},
            "evidence_boundary": "No signed edges passed the requested evidence filters.",
        }

    components = _cyclic_components(graph)
    component_rows = []
    for vertices in components:
        subgraph = graph.induced_subgraph(vertices)
        ids = subgraph.vs["gene_id"]
        edge_count = subgraph.ecount()
        mean_confidence = sum(subgraph.es["confidence"]) / edge_count
        density = edge_count / max(len(ids) * len(ids), 1)
        core_score = min(1.0, 0.50 * mean_confidence + 0.30 * min(1.0, edge_count / max(2 * len(ids), 1))
                         + 0.20 * min(1.0, math.log1p(len(ids)) / math.log(101)))
        core_id = hashlib.sha256(
            f"{species}|{'|'.join(sorted(ids))}".encode("utf-8")
        ).hexdigest()[:20]
        component_rows.append(
            (core_score, core_id, vertices, ids, mean_confidence, density, edge_count)
        )
    component_rows.sort(key=lambda row: (-row[0], -len(row[3]), row[1]))

    cores = []
    all_circuits = 0
    any_search_truncated = False
    circuits_globally_truncated = False
    for rank, (core_score, core_id, vertices, ids, mean_confidence, density, edge_count) in enumerate(
        component_rows[:params.max_cores], start=1
    ):
        remaining = params.max_circuits - all_circuits
        subgraph = graph.induced_subgraph(vertices)
        if remaining <= 0:
            circuits_globally_truncated = True
            circuits = []
            search = {
                "search_states": 0,
                "candidate_circuits": 0,
                "returned_circuits": 0,
                "state_budget_hit": False,
                "candidate_cap_hit": False,
                "truncated": True,
                "reason": "global representative-circuit display limit reached",
            }
        else:
            local_params = FeedbackParameters(**{
                **asdict(params),
                "circuits_per_core": min(params.circuits_per_core, remaining),
            })
            circuits, search = _representative_cycles(
                subgraph, genes, core_id, local_params,
            )
            search["reason"] = None
        _hydrate_circuit_provenance(conn, circuits)
        circuits.sort(key=lambda circuit: (-circuit["score"], circuit["length"], circuit["circuit_id"]))
        backbone_edges = _backbone_edges(subgraph)
        _hydrate_edge_provenance(conn, backbone_edges)
        catalog_cycles, cycle_catalog = _exact_cycle_catalog(
            subgraph, genes, core_id, params,
        )
        cover_cycles, cycle_cover = _compact_cycle_cover(
            subgraph, genes, core_id, params,
        )
        provenance = {
            (edge["source"], edge["target"]): (edge["sources"], edge["pmids"])
            for edge in backbone_edges
        }
        for circuit in [*catalog_cycles, *cover_cycles]:
            for edge in circuit["edges"]:
                edge["sources"], edge["pmids"] = provenance[(edge["source"], edge["target"])]
            score, label, components = _circuit_score(circuit["edges"])
            circuit.update(score=score, confidence_label=label, score_components=components)
        all_circuits += len(circuits)
        any_search_truncated = any_search_truncated or search["truncated"]
        cycle_counts = Counter(
            gene["id"] for circuit in circuits for gene in circuit["genes"]
        )
        controller = _controller_set(subgraph, genes, cycle_counts, params)
        family_counts = Counter(circuit["family"] for circuit in circuits)
        gene_sample = sorted(
            (genes[gene_id] for gene_id in ids),
            key=lambda gene: (-cycle_counts.get(gene["id"], 0), gene["symbol"], gene["id"]),
        )[:25]
        cores.append({
            "core_id": core_id,
            "_gene_ids": list(ids),
            "rank": rank,
            "score": round(core_score, 4),
            "node_count": len(ids),
            "edge_count": edge_count,
            "density": round(density, 6),
            "mean_edge_confidence": round(mean_confidence, 4),
            "family_counts": dict(sorted(family_counts.items())),
            "gene_sample": gene_sample,
            "backbone": {
                "cycle_capable_nodes": len(ids),
                "cycle_capable_edges": len(backbone_edges),
                "complete": True,
            },
            "cycle_catalog": cycle_catalog,
            "cycle_cover": {
                **cycle_cover,
                "circuits": cover_cycles[:25],
                "circuits_returned": min(len(cover_cycles), 25),
                "circuits_total": len(cover_cycles),
            },
            "controller_analysis": controller,
            "circuit_search": search,
            "circuits": circuits,
            "_genes": [genes[gene_id] for gene_id in ids],
            "_backbone_edges": backbone_edges,
            "_catalog_cycles": catalog_cycles,
            "_cycle_cover_cycles": cover_cycles,
        })

    core_relationships, core_groups = _discover_core_relationships(
        graph, genes, cores, params.max_bridge_hops,
    )
    for relationship in core_relationships:
        _hydrate_edge_provenance(conn, relationship["edges"])

    systems = []
    if params.discover_systems:
        systems = control_systems.discover_control_systems(
            conn, species, graph, genes, cores,
            max_systems=params.max_systems,
            max_system_genes=params.max_system_genes,
        )
    feedback_gene_count = sum(len(row[3]) for row in component_rows)
    returned_feedback_genes = sum(core["node_count"] for core in cores)
    return {
        "run_id": run_id,
        "algorithm_version": ALGORITHM_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "species": species,
        "parameters": params.normalized(),
        "graph": {
            "nodes": graph.vcount(),
            "edges": graph.ecount(),
            "graph_hash": graph_hash,
            "signed_evidence_only": True,
        },
        "summary": {
            "feedback_cores": len(component_rows),
            "feedback_cores_returned": len(cores),
            "feedback_genes": feedback_gene_count,
            "feedback_genes_returned": returned_feedback_genes,
            "feedback_edges": sum(row[6] for row in component_rows),
            "feedback_edges_returned": sum(core["edge_count"] for core in cores),
            "exact_cycle_catalogs": sum(core["cycle_catalog"]["exact"] for core in cores),
            "cataloged_cycles": sum(core["cycle_catalog"]["cataloged_cycles"] for core in cores),
            "circuits_returned": all_circuits,
            "controller_candidates": sum(
                len(core["controller_analysis"]["controllers"]) for core in cores
            ),
            "biological_systems": len(systems),
            "annotation_supported_systems": sum(
                system["discovery_mode"] == "annotation_supported" for system in systems
            ),
            "core_relationships": len(core_relationships),
            "core_groups": len(core_groups),
        },
        "systems": systems,
        "cores": cores,
        "core_relationships": core_relationships,
        "core_groups": core_groups,
        "truncation": {
            "cores": len(component_rows) > len(cores),
            "circuits": circuits_globally_truncated or any(
                core["circuit_search"]["truncated"] for core in cores
            ),
            "search": any_search_truncated,
        },
        "evidence_boundary": (
            "Topology identifies candidate control structures, not demonstrated dynamics. "
            "Oscillation, switching, memory, and intervention direction require contextual, kinetic, "
            "or perturbation validation."
        ),
    }


class FeedbackStore:
    """Versioned sidecar store for bounded feedback-analysis results."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS feedback_runs (
                    run_id TEXT PRIMARY KEY,
                    species TEXT NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    graph_hash TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    response_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_runs_species
                    ON feedback_runs(species, generated_at DESC);
                CREATE TABLE IF NOT EXISTS feedback_cores (
                    run_id TEXT NOT NULL,
                    core_id TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    score REAL NOT NULL,
                    node_count INTEGER NOT NULL,
                    edge_count INTEGER NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, core_id),
                    FOREIGN KEY (run_id) REFERENCES feedback_runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS feedback_core_genes (
                    run_id TEXT NOT NULL,
                    core_id TEXT NOT NULL,
                    gene_id TEXT NOT NULL,
                    symbol TEXT,
                    is_controller INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (run_id, core_id, gene_id),
                    FOREIGN KEY (run_id, core_id) REFERENCES feedback_cores(run_id, core_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_core_genes_gene
                    ON feedback_core_genes(gene_id, run_id);
                CREATE TABLE IF NOT EXISTS feedback_core_edges (
                    run_id TEXT NOT NULL,
                    core_id TEXT NOT NULL,
                    edge_index INTEGER NOT NULL,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    sign TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    sign_evidence TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, core_id, edge_index),
                    FOREIGN KEY (run_id, core_id) REFERENCES feedback_cores(run_id, core_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_core_edges_pair
                    ON feedback_core_edges(run_id, core_id, source_id, target_id);
                CREATE TABLE IF NOT EXISTS feedback_circuits (
                    run_id TEXT NOT NULL,
                    circuit_id TEXT NOT NULL,
                    core_id TEXT NOT NULL,
                    family TEXT NOT NULL,
                    polarity TEXT NOT NULL,
                    length INTEGER NOT NULL,
                    score REAL NOT NULL,
                    confidence_label TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, circuit_id),
                    FOREIGN KEY (run_id, core_id) REFERENCES feedback_cores(run_id, core_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_circuits_family
                    ON feedback_circuits(run_id, family, score DESC);
                CREATE TABLE IF NOT EXISTS feedback_circuit_edges (
                    run_id TEXT NOT NULL,
                    circuit_id TEXT NOT NULL,
                    edge_index INTEGER NOT NULL,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    PRIMARY KEY (run_id, circuit_id, edge_index),
                    FOREIGN KEY (run_id, circuit_id) REFERENCES feedback_circuits(run_id, circuit_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS feedback_cycle_catalog (
                    run_id TEXT NOT NULL,
                    core_id TEXT NOT NULL,
                    circuit_id TEXT NOT NULL,
                    catalog_kind TEXT NOT NULL,
                    family TEXT NOT NULL,
                    polarity TEXT NOT NULL,
                    length INTEGER NOT NULL,
                    score REAL NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, core_id, circuit_id, catalog_kind),
                    FOREIGN KEY (run_id, core_id) REFERENCES feedback_cores(run_id, core_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_cycle_catalog_query
                    ON feedback_cycle_catalog(run_id, core_id, polarity, length, score DESC);
                CREATE TABLE IF NOT EXISTS feedback_core_relationships (
                    run_id TEXT NOT NULL,
                    relationship_id TEXT NOT NULL,
                    source_core_id TEXT NOT NULL,
                    target_core_id TEXT NOT NULL,
                    hop_count INTEGER NOT NULL,
                    score REAL NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, relationship_id),
                    FOREIGN KEY (run_id) REFERENCES feedback_runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS feedback_core_groups (
                    run_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    core_count INTEGER NOT NULL,
                    score REAL NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, group_id),
                    FOREIGN KEY (run_id) REFERENCES feedback_runs(run_id) ON DELETE CASCADE
                );
            """)

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT response_json FROM feedback_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def latest(self, species: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT response_json FROM feedback_runs WHERE species = ? "
                "ORDER BY generated_at DESC LIMIT 1", (species,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def backbone(
        self, run_id: str, core_id: str, edge_cursor: int = 0, edge_limit: int = 2_000,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            core = conn.execute(
                "SELECT node_count,edge_count,result_json FROM feedback_cores "
                "WHERE run_id=? AND core_id=?", (run_id, core_id),
            ).fetchone()
            if core is None:
                return None
            gene_rows = conn.execute(
                "SELECT gene_id,symbol,is_controller FROM feedback_core_genes "
                "WHERE run_id=? AND core_id=? ORDER BY gene_id", (run_id, core_id),
            ).fetchall()
            edge_rows = conn.execute(
                "SELECT result_json FROM feedback_core_edges WHERE run_id=? AND core_id=? "
                "ORDER BY edge_index LIMIT ? OFFSET ?",
                (run_id, core_id, edge_limit, edge_cursor),
            ).fetchall()
        next_cursor = edge_cursor + len(edge_rows)
        return {
            "run_id": run_id,
            "core_id": core_id,
            "node_count": int(core[0]),
            "edge_count": int(core[1]),
            "nodes": [
                {"id": row[0], "symbol": row[1] or row[0], "is_controller": bool(row[2])}
                for row in gene_rows
            ],
            "edges": [json.loads(row[0]) for row in edge_rows],
            "edge_cursor": edge_cursor,
            "next_edge_cursor": next_cursor if next_cursor < int(core[1]) else None,
            "complete": next_cursor >= int(core[1]),
            "core": json.loads(core[2]),
        }

    def query_cycles(
        self,
        run_id: str,
        core_id: str,
        *,
        polarity: str | None = None,
        gene_id: str | None = None,
        min_length: int = 1,
        max_length: int | None = None,
        cursor: int = 0,
        limit: int = 50,
        max_examined: int = 100_000,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            core_row = conn.execute(
                "SELECT result_json FROM feedback_cores WHERE run_id=? AND core_id=?",
                (run_id, core_id),
            ).fetchone()
            if core_row is None:
                return None
            core = json.loads(core_row[0])
            catalog = core.get("cycle_catalog", {})
            if catalog.get("exact"):
                rows = conn.execute(
                    "SELECT result_json FROM feedback_cycle_catalog "
                    "WHERE run_id=? AND core_id=? AND catalog_kind='exact' "
                    "ORDER BY length,circuit_id",
                    (run_id, core_id),
                ).fetchall()
                matching = []
                for row in rows:
                    circuit = json.loads(row[0])
                    if polarity and circuit["polarity"] != polarity:
                        continue
                    if circuit["length"] < min_length:
                        continue
                    if max_length is not None and circuit["length"] > max_length:
                        continue
                    if gene_id and all(gene["id"] != gene_id for gene in circuit["genes"]):
                        continue
                    matching.append(circuit)
                page = matching[cursor:cursor + limit]
                next_cursor = cursor + len(page)
                return {
                    "run_id": run_id,
                    "core_id": core_id,
                    "mode": "exact_catalog",
                    "cycles": page,
                    "cursor": cursor,
                    "next_cursor": next_cursor if next_cursor < len(matching) else None,
                    "matching_cycles": len(matching),
                    "examined_cycles": len(rows),
                    "complete": next_cursor >= len(matching),
                    "exhaustive_catalog": True,
                }

            gene_rows = conn.execute(
                "SELECT gene_id,symbol FROM feedback_core_genes "
                "WHERE run_id=? AND core_id=? ORDER BY gene_id", (run_id, core_id),
            ).fetchall()
            edge_rows = conn.execute(
                "SELECT result_json "
                "FROM feedback_core_edges WHERE run_id=? AND core_id=? ORDER BY edge_index",
                (run_id, core_id),
            ).fetchall()

        genes = {
            row[0]: {"id": row[0], "symbol": row[1] or row[0], "name": None,
                     "is_tf": False, "species": None}
            for row in gene_rows
        }
        node_ids = sorted(genes)
        node_index = {gene_id: index for index, gene_id in enumerate(node_ids)}
        edge_records = [json.loads(row[0]) for row in edge_rows]
        graph = ig.Graph(n=len(node_ids), directed=True)
        graph.vs["gene_id"] = node_ids
        graph.add_edges(
            [(node_index[edge["source"]], node_index[edge["target"]]) for edge in edge_records],
            attributes={
                "confidence": [float(edge["confidence"]) for edge in edge_records],
                "repression": [edge["sign"] == "repression" for edge in edge_records],
                "measured": [edge["sign_evidence"] == "measured" for edge in edge_records],
            },
        )
        directed = nx.DiGraph()
        directed.add_nodes_from(node_ids)
        directed.add_edges_from((edge["source"], edge["target"]) for edge in edge_records)
        provenance = {
            (edge["source"], edge["target"]): (edge.get("sources", []), edge.get("pmids", []))
            for edge in edge_records
        }
        iterator = nx.simple_cycles(directed, length_bound=max_length)
        cycles = []
        raw_index = 0
        examined = 0
        exhausted = True
        for cycle in iterator:
            if raw_index < cursor:
                raw_index += 1
                continue
            if examined >= max_examined:
                exhausted = False
                break
            raw_index += 1
            examined += 1
            if len(cycle) < min_length:
                continue
            if gene_id and gene_id not in cycle:
                continue
            record = _cycle_record(
                graph, [node_index[item] for item in cycle], genes, core_id,
            )
            for edge in record["edges"]:
                edge["sources"], edge["pmids"] = provenance[(edge["source"], edge["target"])]
            score, label, components = _circuit_score(record["edges"])
            record.update(score=score, confidence_label=label, score_components=components)
            if polarity and record["polarity"] != polarity:
                continue
            cycles.append(record)
            if len(cycles) >= limit:
                exhausted = False
                break
        return {
            "run_id": run_id,
            "core_id": core_id,
            "mode": "on_demand_enumeration",
            "cycles": cycles,
            "cursor": cursor,
            "next_cursor": None if exhausted else raw_index,
            "matching_cycles": None,
            "examined_cycles": examined,
            "complete": exhausted,
            "exhaustive_catalog": False,
            "boundary": (
                "Continue with next_cursor to enumerate additional simple cycles. "
                "Completion is exact, but dense cores may contain an impractical number of cycles."
            ),
        }

    def save(self, result: dict[str, Any]) -> None:
        run_id = result["run_id"]
        generated_at = result.get("generated_at") or datetime.now(timezone.utc).isoformat()
        public_result = _public_result(result)
        public_cores = {core["core_id"]: core for core in public_result["cores"]}
        with self._connect() as conn:
            conn.execute("DELETE FROM feedback_runs WHERE run_id = ?", (run_id,))
            conn.execute(
                "INSERT INTO feedback_runs VALUES (?,?,?,?,?,?,?)",
                (
                    run_id, result["species"], result["algorithm_version"],
                    result["graph"]["graph_hash"],
                    json.dumps(result["parameters"], sort_keys=True), generated_at,
                    json.dumps(public_result, separators=(",", ":")),
                ),
            )
            for core in result["cores"]:
                conn.execute(
                    "INSERT INTO feedback_cores VALUES (?,?,?,?,?,?,?)",
                    (run_id, core["core_id"], core["rank"], core["score"],
                     core["node_count"], core["edge_count"],
                     json.dumps(public_cores[core["core_id"]], separators=(",", ":"))),
                )
                controllers = {
                    gene["id"] for gene in core["controller_analysis"]["controllers"]
                }
                core_genes = {
                    gene["id"]: gene for gene in core.get("_genes", [])
                }
                core_genes.update({gene["id"]: gene for gene in core["gene_sample"]})
                for circuit in core["circuits"]:
                    for gene in circuit["genes"]:
                        core_genes[gene["id"]] = gene
                for gene_id in controllers:
                    if gene_id not in core_genes:
                        core_genes[gene_id] = next(
                            gene for gene in core["controller_analysis"]["controllers"]
                            if gene["id"] == gene_id
                        )
                conn.executemany(
                    "INSERT INTO feedback_core_genes VALUES (?,?,?,?,?)",
                    [(run_id, core["core_id"], gene_id, gene.get("symbol"), int(gene_id in controllers))
                     for gene_id, gene in core_genes.items()],
                )
                conn.executemany(
                    "INSERT INTO feedback_core_edges VALUES (?,?,?,?,?,?,?,?,?)",
                    [
                        (
                            run_id, core["core_id"], index, edge["source"], edge["target"],
                            edge["sign"], edge["confidence"], edge["sign_evidence"],
                            json.dumps(edge, separators=(",", ":")),
                        )
                        for index, edge in enumerate(core.get("_backbone_edges", []))
                    ],
                )
                for circuit in core["circuits"]:
                    conn.execute(
                        "INSERT INTO feedback_circuits VALUES (?,?,?,?,?,?,?,?,?)",
                        (run_id, circuit["circuit_id"], core["core_id"], circuit["family"],
                         circuit["polarity"], circuit["length"], circuit["score"],
                         circuit["confidence_label"], json.dumps(circuit, separators=(",", ":"))),
                    )
                    conn.executemany(
                        "INSERT INTO feedback_circuit_edges VALUES (?,?,?,?,?)",
                        [(run_id, circuit["circuit_id"], index, edge["source"], edge["target"])
                         for index, edge in enumerate(circuit["edges"])],
                    )
                catalog_rows = []
                for kind, rows in (
                    ("exact", core.get("_catalog_cycles", [])),
                    ("cover", core.get("_cycle_cover_cycles", [])),
                ):
                    catalog_rows.extend(
                        (
                            run_id, core["core_id"], circuit["circuit_id"], kind,
                            circuit["family"], circuit["polarity"], circuit["length"],
                            circuit["score"], json.dumps(circuit, separators=(",", ":")),
                        )
                        for circuit in rows
                    )
                conn.executemany(
                    "INSERT INTO feedback_cycle_catalog VALUES (?,?,?,?,?,?,?,?,?)",
                    catalog_rows,
                )
            conn.executemany(
                "INSERT INTO feedback_core_relationships VALUES (?,?,?,?,?,?,?)",
                [
                    (
                        run_id, row["relationship_id"], row["source_core_id"],
                        row["target_core_id"], row["hop_count"], row["score"],
                        json.dumps(row, separators=(",", ":")),
                    )
                    for row in result.get("core_relationships", [])
                ],
            )
            conn.executemany(
                "INSERT INTO feedback_core_groups VALUES (?,?,?,?,?,?)",
                [
                    (
                        run_id, row["group_id"], row["rank"], row["core_count"],
                        row["score"], json.dumps(row, separators=(",", ":")),
                    )
                    for row in result.get("core_groups", [])
                ],
            )


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    """Remove persistence-only fields without copying large nested circuit data."""
    return {
        **result,
        "cores": [
            {key: value for key, value in core.items() if not key.startswith("_")}
            for core in result["cores"]
        ],
    }


def analyze_and_store(
    conn: sqlite3.Connection,
    store: FeedbackStore,
    species: str,
    params: FeedbackParameters | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    result = analyze_feedback(conn, species, params)
    if not refresh:
        cached = store.get(result["run_id"])
        if cached is not None:
            cached["storage"] = {"status": "cached", "backend": "versioned_sidecar"}
            return cached
    store.save(result)
    public_result = _public_result(result)
    public_result["storage"] = {"status": "stored", "backend": "versioned_sidecar"}
    return public_result
