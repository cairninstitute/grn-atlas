"""Independent verification harness for bounded signed-feedback analysis."""

from __future__ import annotations

import itertools
import json
import random
import sqlite3
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Iterable

import igraph as ig
import networkx as nx

from feedback_control import (
    FeedbackStore,
    FeedbackParameters,
    _circuit_score,
    _controller_set,
    analyze_feedback,
    analyze_and_store,
)


VERIFICATION_VERSION = "feedback-verification-v1"


REFERENCE_CIRCUITS = (
    {
        "name": "human NF-kB inhibitor feedback",
        "species": "human",
        "genes": ("NFKB1", "NFKBIA"),
        "edges": (("NFKB1", "NFKBIA", "activation"), ("NFKBIA", "NFKB1", "repression")),
        "expected_family": "negative_feedback",
        "expected_polarity": "negative",
    },
    {
        "name": "human E2F-MYC mutual activation",
        "species": "human",
        "genes": ("E2F1", "MYC"),
        "edges": (("E2F1", "MYC", "activation"), ("MYC", "E2F1", "activation")),
        "expected_family": "mutual_activation",
        "expected_polarity": "positive",
    },
    {
        "name": "human E2F-RB negative feedback",
        "species": "human",
        "genes": ("E2F1", "RB1"),
        "edges": (("E2F1", "RB1", "activation"), ("RB1", "E2F1", "repression")),
        "expected_family": "negative_feedback",
        "expected_polarity": "negative",
    },
    {
        "name": "mouse p53-Mdm2 negative feedback",
        "species": "mouse",
        "genes": ("Trp53", "Mdm2"),
        "edges": (("Trp53", "Mdm2", "activation"), ("Mdm2", "Trp53", "repression")),
        "expected_family": "negative_feedback",
        "expected_polarity": "negative",
    },
    {
        "name": "Arabidopsis LHY-LUX/PCL1 negative feedback",
        "species": "arabidopsis",
        "genes": ("LHY", "PCL1"),
        "edges": (("LHY", "PCL1", "repression"), ("PCL1", "LHY", "activation")),
        "expected_family": "negative_feedback",
        "expected_polarity": "negative",
    },
    {
        "name": "Arabidopsis CCA1-LUX/PCL1 negative feedback",
        "species": "arabidopsis",
        "genes": ("CCA1", "PCL1"),
        "edges": (("CCA1", "PCL1", "repression"), ("PCL1", "CCA1", "activation")),
        "expected_family": "negative_feedback",
        "expected_polarity": "negative",
    },
)


CLOCK_ARMS = (
    {
        "name": "morning represses evening",
        "alternatives": (
            ("CCA1", "TOC1", "repression"),
            ("LHY", "TOC1", "repression"),
            ("CCA1", "PCL1", "repression"),
            ("LHY", "PCL1", "repression"),
        ),
    },
    {
        "name": "evening regulates daytime PRRs",
        "alternatives": (
            ("PCL1", "PRR9", "repression"),
            ("PCL1", "PRR7", "repression"),
        ),
    },
    {
        "name": "daytime PRRs repress morning",
        "alternatives": (
            ("PRR9", "CCA1", "repression"),
            ("PRR9", "LHY", "repression"),
            ("PRR7", "CCA1", "repression"),
            ("PRR7", "LHY", "repression"),
            ("PRR5", "CCA1", "repression"),
            ("PRR5", "LHY", "repression"),
        ),
    },
)


def canonical_cycle(nodes: Iterable[str]) -> tuple[str, ...]:
    values = list(nodes)
    if len(values) == 1:
        return (values[0],)
    return min(tuple(values[index:] + values[:index]) for index in range(len(values)))


def fixture_connection(nodes: Iterable[str], edges: Iterable[tuple[str, str, str]]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE genes (
            id TEXT PRIMARY KEY, symbol TEXT, name TEXT, species TEXT, is_tf INTEGER
        );
        CREATE TABLE interactions (
            source_id TEXT, target_id TEXT, regulation_type TEXT, confidence REAL,
            sources TEXT, pmids TEXT, sign TEXT, sign_evidence TEXT, sign_r REAL,
            PRIMARY KEY (source_id, target_id)
        );
    """)
    node_list = sorted(set(nodes))
    conn.executemany(
        "INSERT INTO genes VALUES (?,?,?,?,?)",
        ((node, node, node, "verification", 1) for node in node_list),
    )
    conn.executemany(
        "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?,?)",
        ((source, target, sign, 0.9, '["verification"]', "[]", sign, "measured", None)
         for source, target, sign in edges),
    )
    return conn


def _nx_graph(nodes: Iterable[str], edges: Iterable[tuple[str, str, str]]) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((source, target, {"sign": sign}) for source, target, sign in edges)
    return graph


def _truth_cores(graph: nx.DiGraph) -> set[frozenset[str]]:
    return {
        frozenset(component)
        for component in nx.strongly_connected_components(graph)
        if len(component) > 1 or graph.has_edge(next(iter(component)), next(iter(component)))
    }


def _truth_cycles(graph: nx.DiGraph, max_length: int) -> dict[tuple[str, ...], str]:
    cycles = {}
    for cycle in nx.simple_cycles(graph, length_bound=max_length):
        key = canonical_cycle(cycle)
        repression_count = sum(
            graph.edges[cycle[index], cycle[(index + 1) % len(cycle)]]["sign"] == "repression"
            for index in range(len(cycle))
        )
        cycles[key] = "negative" if repression_count % 2 else "positive"
    return cycles


def _brute_force_fvs(graph: nx.DiGraph) -> tuple[str, ...]:
    nodes = sorted(graph.nodes)
    for size in range(len(nodes) + 1):
        for removed in itertools.combinations(nodes, size):
            if nx.is_directed_acyclic_graph(graph.subgraph(set(nodes) - set(removed))):
                return removed
    raise AssertionError("a feedback vertex set must exist")


def _fixture_catalog(seed: int = 20261012, random_graphs: int = 30) -> list[dict[str, Any]]:
    fixtures = [
        {"name": "self-loops", "nodes": list("ABC"),
         "edges": [("A", "A", "activation"), ("B", "B", "repression"), ("A", "C", "activation")]},
        {"name": "reciprocal-and-ring", "nodes": list("ABCDE"),
         "edges": [("A", "B", "repression"), ("B", "A", "repression"),
                   ("C", "D", "repression"), ("D", "E", "repression"), ("E", "C", "repression")]},
        {"name": "overlapping-cycles", "nodes": list("ABCDEF"),
         "edges": [("A", "B", "activation"), ("B", "C", "repression"),
                   ("C", "A", "activation"), ("C", "D", "repression"),
                   ("D", "B", "activation"), ("E", "F", "activation")]},
        {"name": "dense-five", "nodes": list("ABCDE"),
         "edges": [(source, target, "repression" if (ord(source) + ord(target)) % 3 == 0 else "activation")
                   for source in "ABCDE" for target in "ABCDE" if source != target]},
        {"name": "greedy-fvs-gap", "nodes": list("0123456"),
         "edges": [(source, target, "activation") for source, target in (
             ("0", "1"), ("0", "3"), ("0", "5"), ("1", "1"), ("1", "5"),
             ("2", "1"), ("2", "2"), ("2", "5"), ("2", "6"), ("3", "2"),
             ("3", "5"), ("4", "1"), ("4", "4"), ("4", "5"), ("4", "6"),
             ("5", "1"), ("5", "4"), ("5", "6"), ("6", "0"), ("6", "3"),
             ("6", "6"),
         )]},
    ]
    rng = random.Random(seed)
    for ordinal in range(random_graphs):
        size = rng.randint(3, 8)
        nodes = [f"R{ordinal:02d}_{index}" for index in range(size)]
        edges = []
        probability = rng.uniform(0.14, 0.38)
        for source in nodes:
            for target in nodes:
                if rng.random() < probability:
                    edges.append((source, target, rng.choice(("activation", "repression"))))
        fixtures.append({"name": f"random-{ordinal:02d}", "nodes": nodes, "edges": edges})
    return fixtures


def verify_structural_truth() -> dict[str, Any]:
    totals = {"expected_cores": 0, "returned_cores": 0, "expected_cycles": 0,
              "returned_cycles": 0, "matched_cores": 0, "matched_cycles": 0,
              "matched_polarity": 0, "exact_fvs_cases": 0, "exact_fvs_optimal": 0,
              "exact_fvs_acyclic": 0, "greedy_fvs_cases": 0, "greedy_fvs_acyclic": 0}
    greedy_ratios = []
    failures = []
    for fixture in _fixture_catalog():
        graph = _nx_graph(fixture["nodes"], fixture["edges"])
        truth_cores = _truth_cores(graph)
        truth_cycles = _truth_cycles(graph, 6)
        params = FeedbackParameters(
            max_loop_length=6, max_cores=100, max_circuits=100_000,
            circuits_per_core=100_000, max_search_states=5_000_000,
            max_controllers=100,
        )
        first = analyze_feedback(fixture_connection(fixture["nodes"], fixture["edges"]), "verification", params)
        second = analyze_feedback(fixture_connection(fixture["nodes"], fixture["edges"]), "verification", params)
        actual_cores = {frozenset(core["_gene_ids"]) for core in first["cores"]}
        actual_cycles = {
            canonical_cycle(gene["id"] for gene in circuit["genes"]): circuit["polarity"]
            for core in first["cores"] for circuit in core["circuits"]
        }
        totals["expected_cores"] += len(truth_cores)
        totals["returned_cores"] += len(actual_cores)
        totals["expected_cycles"] += len(truth_cycles)
        totals["returned_cycles"] += len(actual_cycles)
        totals["matched_cores"] += len(truth_cores & actual_cores)
        totals["matched_cycles"] += len(truth_cycles.keys() & actual_cycles.keys())
        totals["matched_polarity"] += sum(
            actual_cycles.get(cycle) == polarity for cycle, polarity in truth_cycles.items()
        )
        comparable_first = {key: value for key, value in first.items() if key != "generated_at"}
        comparable_second = {key: value for key, value in second.items() if key != "generated_at"}
        if comparable_first != comparable_second:
            failures.append({"fixture": fixture["name"], "category": "nondeterministic"})
        if truth_cores != actual_cores:
            failures.append({"fixture": fixture["name"], "category": "core_mismatch"})
        if truth_cycles != actual_cycles:
            failures.append({"fixture": fixture["name"], "category": "cycle_or_polarity_mismatch"})

        for component in truth_cores:
            subgraph = graph.subgraph(component).copy()
            optimum = _brute_force_fvs(subgraph)
            core = next(core for core in first["cores"] if set(core["_gene_ids"]) == set(component))
            exact = [gene["id"] for gene in core["controller_analysis"]["controllers"]]
            totals["exact_fvs_cases"] += 1
            totals["exact_fvs_optimal"] += len(exact) == len(optimum)
            totals["exact_fvs_acyclic"] += nx.is_directed_acyclic_graph(
                subgraph.subgraph(set(component) - set(exact))
            )

            ids = sorted(component)
            index = {gene_id: position for position, gene_id in enumerate(ids)}
            igraph = ig.Graph(n=len(ids), directed=True)
            igraph.vs["gene_id"] = ids
            igraph.add_edges((index[source], index[target]) for source, target in subgraph.edges)
            genes = {gene_id: {"id": gene_id, "symbol": gene_id} for gene_id in ids}
            greedy = _controller_set(
                igraph, genes, {}, FeedbackParameters(exact_controller_max_nodes=0, max_controllers=len(ids)),
            )
            greedy_ids = [gene["id"] for gene in greedy["controllers"]]
            totals["greedy_fvs_cases"] += 1
            totals["greedy_fvs_acyclic"] += nx.is_directed_acyclic_graph(
                subgraph.subgraph(set(component) - set(greedy_ids))
            )
            greedy_ratios.append(len(greedy_ids) / max(len(optimum), 1))

    cycle_denominator = max(totals["expected_cycles"], 1)
    core_denominator = max(totals["expected_cores"], 1)
    return {
        "fixture_count": len(_fixture_catalog()),
        **totals,
        "core_recall": round(totals["matched_cores"] / core_denominator, 4),
        "core_precision": round(totals["matched_cores"] / max(totals["returned_cores"], 1), 4),
        "cycle_recall": round(totals["matched_cycles"] / cycle_denominator, 4),
        "cycle_precision": round(totals["matched_cycles"] / max(totals["returned_cycles"], 1), 4),
        "polarity_accuracy": round(totals["matched_polarity"] / cycle_denominator, 4),
        "exact_fvs_optimal_rate": round(totals["exact_fvs_optimal"] / max(totals["exact_fvs_cases"], 1), 4),
        "greedy_fvs_mean_size_ratio": round(sum(greedy_ratios) / max(len(greedy_ratios), 1), 4),
        "greedy_fvs_max_size_ratio": round(max(greedy_ratios, default=0.0), 4),
        "failures": failures,
    }


def _resolve_symbols(conn: sqlite3.Connection, species: str, symbols: Iterable[str]) -> dict[str, str]:
    values = sorted(set(symbols))
    placeholders = ",".join("?" for _ in values)
    rows = conn.execute(
        f"SELECT symbol, id FROM genes WHERE species = ? AND symbol IN ({placeholders})",
        (species, *values),
    ).fetchall()
    return {symbol: gene_id for symbol, gene_id in rows}


def _edge_lookup(conn: sqlite3.Connection, source_id: str, target_id: str) -> tuple[str, str, float] | None:
    return conn.execute(
        "SELECT sign, sign_evidence, confidence FROM interactions "
        "WHERE source_id = ? AND target_id = ? AND sign IN ('activation','repression') "
        "AND sign_evidence IN ('measured','perturbation') AND confidence >= 0.5",
        (source_id, target_id),
    ).fetchone()


def verify_biological_recovery(conn: sqlite3.Connection) -> dict[str, Any]:
    analyses = {
        species: analyze_feedback(
            conn, species, FeedbackParameters(
                max_cores=200, max_circuits=10_000, circuits_per_core=10_000,
                max_search_states=2_000_000, max_controllers=200,
            ),
        )
        for species in sorted({case["species"] for case in REFERENCE_CIRCUITS})
    }
    rows = []
    for case in REFERENCE_CIRCUITS:
        symbols = {symbol for edge in case["edges"] for symbol in edge[:2]}
        resolved = _resolve_symbols(conn, case["species"], symbols)
        edge_checks = []
        for source, target, expected_sign in case["edges"]:
            observed = _edge_lookup(conn, resolved.get(source, ""), resolved.get(target, ""))
            edge_checks.append({
                "source": source, "target": target, "expected_sign": expected_sign,
                "observed_sign": observed[0] if observed else None,
                "present_with_expected_sign": bool(observed and observed[0] == expected_sign),
            })
        coverage_complete = len(resolved) == len(symbols) and all(
            edge["present_with_expected_sign"] for edge in edge_checks
        )
        expected_ids = frozenset(resolved.values())
        result = analyses[case["species"]]
        core_recovered = any(expected_ids <= set(core["_gene_ids"]) for core in result["cores"])
        matching = [
            circuit for core in result["cores"] for circuit in core["circuits"]
            if frozenset(gene["id"] for gene in circuit["genes"]) == expected_ids
            and circuit["length"] == len(expected_ids)
        ]
        circuit_recovered = any(
            circuit["family"] == case["expected_family"]
            and circuit["polarity"] == case["expected_polarity"]
            for circuit in matching
        )
        if not coverage_complete:
            attribution = "atlas_coverage"
        elif not core_recovered:
            attribution = "core_detection"
        elif not circuit_recovered:
            attribution = "circuit_retrieval"
        else:
            attribution = "recovered"
        rows.append({
            **{key: case[key] for key in ("name", "species", "expected_family", "expected_polarity")},
            "edge_coverage_complete": coverage_complete,
            "core_recovered": core_recovered,
            "circuit_recovered": circuit_recovered,
            "attribution": attribution,
            "edges": edge_checks,
        })

    clock_symbols = {symbol for arm in CLOCK_ARMS for edge in arm["alternatives"] for symbol in edge[:2]}
    clock_ids = _resolve_symbols(conn, "arabidopsis", clock_symbols)
    clock_rows = []
    for arm in CLOCK_ARMS:
        alternatives = []
        for source, target, sign in arm["alternatives"]:
            observed = _edge_lookup(conn, clock_ids.get(source, ""), clock_ids.get(target, ""))
            alternatives.append({
                "source": source, "target": target, "expected_sign": sign,
                "observed_sign": observed[0] if observed else None,
                "supported": bool(observed and observed[0] == sign),
            })
        clock_rows.append({
            "name": arm["name"], "supported": any(row["supported"] for row in alternatives),
            "alternatives": alternatives,
        })
    fully_covered = [row for row in rows if row["edge_coverage_complete"]]
    recovered = [row for row in fully_covered if row["circuit_recovered"]]
    return {
        "reference_circuits": rows,
        "summary": {
            "cases": len(rows),
            "fully_covered": len(fully_covered),
            "recovered": len(recovered),
            "recovery_rate_when_covered": round(len(recovered) / max(len(fully_covered), 1), 4),
        },
        "arabidopsis_clock_architecture": {
            "arms": clock_rows,
            "supported_arms": sum(row["supported"] for row in clock_rows),
            "total_arms": len(clock_rows),
            "closed_three_module_loop_recoverable": all(row["supported"] for row in clock_rows),
        },
    }


def _pathology(name: str, nodes: list[str], edges: list[tuple[str, str, str]],
               params: FeedbackParameters) -> dict[str, Any]:
    started = time.perf_counter()
    result = analyze_feedback(fixture_connection(nodes, edges), "verification", params)
    return {
        "name": name,
        "nodes": len(nodes),
        "edges": len(edges),
        "seconds": round(time.perf_counter() - started, 4),
        "feedback_cores": result["summary"]["feedback_cores"],
        "circuits_returned": result["summary"]["circuits_returned"],
        "truncation": result["truncation"],
        "bounded": result["summary"]["circuits_returned"] <= params.max_circuits,
    }


def verify_robustness() -> dict[str, Any]:
    large_nodes = [f"L{i:04d}" for i in range(1_000)]
    large_edges = [
        (large_nodes[index], large_nodes[(index + step) % len(large_nodes)], "repression" if step == 7 else "activation")
        for index in range(len(large_nodes)) for step in (1, 7, 31)
    ]
    pair_nodes = [f"P{i:04d}" for i in range(600)]
    pair_edges = [
        (pair_nodes[index], pair_nodes[index + direction], "repression")
        for index in range(0, len(pair_nodes), 2) for direction in (1,)
    ] + [
        (pair_nodes[index + 1], pair_nodes[index], "activation")
        for index in range(0, len(pair_nodes), 2)
    ]
    dense_nodes = [f"D{i:02d}" for i in range(30)]
    dense_edges = [
        (source, target, "repression" if (i + j) % 4 == 0 else "activation")
        for i, source in enumerate(dense_nodes) for j, target in enumerate(dense_nodes)
        if source != target
    ]
    params = FeedbackParameters(
        max_cores=500, max_circuits=100, circuits_per_core=12,
        max_search_states=2_000, max_controllers=10,
    )
    cases = [
        _pathology("large-scc", large_nodes, large_edges, params),
        _pathology("many-small-sccs", pair_nodes, pair_edges, params),
        _pathology("dense-core", dense_nodes, dense_edges, params),
        _pathology("acyclic", [f"A{i}" for i in range(200)],
                   [(f"A{i}", f"A{i + 1}", "activation") for i in range(199)], params),
    ]
    return {"cases": cases, "all_bounded": all(case["bounded"] for case in cases)}


def verify_scoring() -> dict[str, Any]:
    def edge(confidence: float, evidence: str = "measured", sources: list[str] | None = None) -> dict[str, Any]:
        return {
            "sign": "activation", "confidence": confidence,
            "sign_evidence": evidence, "sources": sources or [],
        }

    low, low_label, _ = _circuit_score([edge(0.6), edge(0.7)])
    high, high_label, _ = _circuit_score([edge(0.8), edge(0.9)])
    perturbation, _, _ = _circuit_score([
        edge(0.8, "perturbation"), edge(0.9, "perturbation"),
    ])
    sourced, _, _ = _circuit_score([
        edge(0.8, sources=["a", "b"]), edge(0.9, sources=["a", "b"]),
    ])
    return {
        "confidence_monotonic": low < high,
        "measured_scores_above_perturbation": perturbation < high,
        "independent_sources_increase_score": high < sourced,
        "labels_consistent": low_label == "supported" and high_label == "high",
        "example_scores": {
            "lower_confidence": low, "higher_confidence": high,
            "perturbation_evidence": perturbation, "additional_sources": sourced,
        },
        "calibration": "heuristic_not_probability",
    }


def verify_persistence() -> dict[str, Any]:
    conn = fixture_connection(
        list("ABC"), [("A", "B", "activation"), ("B", "A", "repression")],
    )
    with tempfile.TemporaryDirectory(prefix="feedback-verification-") as directory:
        store = FeedbackStore(f"{directory}/feedback.sqlite3")
        first = analyze_and_store(conn, store, "verification")
        cached = analyze_and_store(conn, store, "verification")
        parameter_change = analyze_feedback(
            conn, "verification", FeedbackParameters(min_confidence=0.7),
        )
        conn.execute("UPDATE interactions SET confidence = 0.8 WHERE source_id = 'A'")
        graph_change = analyze_feedback(conn, "verification")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(store.save, graph_change) for _ in range(4)]
            for future in futures:
                future.result()
        with sqlite3.connect(store.path) as persisted:
            foreign_key_errors = persisted.execute("PRAGMA foreign_key_check").fetchall()
            complete_membership = persisted.execute(
                "SELECT COUNT(*) FROM feedback_core_genes WHERE run_id = ?",
                (graph_change["run_id"],),
            ).fetchone()[0] == graph_change["summary"]["feedback_genes"]
        return {
            "cache_reused": cached["storage"]["status"] == "cached" and cached["run_id"] == first["run_id"],
            "parameter_change_invalidates": parameter_change["run_id"] != first["run_id"],
            "graph_change_invalidates": graph_change["run_id"] != first["run_id"],
            "foreign_keys_consistent_after_concurrent_writes": foreign_key_errors == [],
            "complete_core_membership_persisted": complete_membership,
        }


def run_verification(conn: sqlite3.Connection) -> dict[str, Any]:
    structural = verify_structural_truth()
    biological = verify_biological_recovery(conn)
    robustness = verify_robustness()
    scoring = verify_scoring()
    persistence = verify_persistence()
    gates = {
        "core_recall_complete": structural["core_recall"] == 1.0,
        "core_precision_complete": structural["core_precision"] == 1.0,
        "cycle_recall_complete": structural["cycle_recall"] == 1.0,
        "cycle_precision_complete": structural["cycle_precision"] == 1.0,
        "polarity_exact": structural["polarity_accuracy"] == 1.0,
        "exact_fvs_optimal": structural["exact_fvs_optimal_rate"] == 1.0,
        "exact_fvs_acyclic": structural["exact_fvs_acyclic"] == structural["exact_fvs_cases"],
        "greedy_fvs_acyclic": structural["greedy_fvs_acyclic"] == structural["greedy_fvs_cases"],
        "covered_biological_circuits_recovered": biological["summary"]["recovery_rate_when_covered"] == 1.0,
        "pathological_cases_bounded": robustness["all_bounded"],
        "score_behavior_consistent": all(
            scoring[key] for key in (
                "confidence_monotonic", "measured_scores_above_perturbation",
                "independent_sources_increase_score", "labels_consistent",
            )
        ),
        "persistence_consistent": all(persistence.values()),
    }
    return {
        "verification_version": VERIFICATION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm_parameters": asdict(FeedbackParameters()),
        "status": "pass" if all(gates.values()) else "fail",
        "gates": gates,
        "structural_truth": structural,
        "biological_recovery": biological,
        "robustness": robustness,
        "scoring": scoring,
        "persistence": persistence,
        "limitations": [
            "Circuit confidence scores are heuristic rankings, not calibrated probabilities.",
            "Complete small-graph recall does not make bounded large-graph cycle output exhaustive.",
            "Structural feedback does not establish switching, homeostasis, or oscillation dynamics.",
        ],
    }
