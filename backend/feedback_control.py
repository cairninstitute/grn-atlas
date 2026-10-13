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

import control_systems


ALGORITHM_VERSION = "feedback-control-v2"
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


def _hydrate_circuit_provenance(
    conn: sqlite3.Connection,
    circuits: Iterable[dict[str, Any]],
) -> None:
    for circuit in circuits:
        for edge in circuit["edges"]:
            row = conn.execute(
                "SELECT sources, pmids FROM interactions WHERE source_id = ? AND target_id = ?",
                (edge["source"], edge["target"]),
            ).fetchone()
            if row:
                edge["sources"] = _json_list(row[0])
                edge["pmids"] = _json_list(row[1])
        score, label, components = _circuit_score(circuit["edges"])
        circuit["score"] = score
        circuit["confidence_label"] = label
        circuit["score_components"] = components


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
                "circuits_returned": 0, "controller_candidates": 0,
                "biological_systems": 0,
            },
            "cores": [],
            "systems": [],
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
        if remaining <= 0:
            circuits_globally_truncated = True
            break
        subgraph = graph.induced_subgraph(vertices)
        local_params = FeedbackParameters(**{
            **asdict(params),
            "circuits_per_core": min(params.circuits_per_core, remaining),
        })
        circuits, search = _representative_cycles(
            subgraph, genes, core_id, local_params,
        )
        _hydrate_circuit_provenance(conn, circuits)
        circuits.sort(key=lambda circuit: (-circuit["score"], circuit["length"], circuit["circuit_id"]))
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
            "controller_analysis": controller,
            "circuit_search": search,
            "circuits": circuits,
        })

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
            "circuits_returned": all_circuits,
            "controller_candidates": sum(
                len(core["controller_analysis"]["controllers"]) for core in cores
            ),
            "biological_systems": len(systems),
            "annotation_supported_systems": sum(
                system["discovery_mode"] == "annotation_supported" for system in systems
            ),
        },
        "systems": systems,
        "cores": cores,
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
                    gene_id: {"id": gene_id, "symbol": None}
                    for gene_id in core.get("_gene_ids", [])
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
