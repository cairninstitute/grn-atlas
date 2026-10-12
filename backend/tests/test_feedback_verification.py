import concurrent.futures
import sqlite3

from fastapi.testclient import TestClient

import feedback_control
import feedback_verification
import main


def test_independent_small_graph_truth_and_controller_quality():
    result = feedback_verification.verify_structural_truth()
    assert result["core_recall"] == 1.0
    assert result["core_precision"] == 1.0
    assert result["cycle_recall"] == 1.0
    assert result["cycle_precision"] == 1.0
    assert result["polarity_accuracy"] == 1.0
    assert result["exact_fvs_optimal_rate"] == 1.0
    assert result["exact_fvs_acyclic"] == result["exact_fvs_cases"]
    assert result["greedy_fvs_acyclic"] == result["greedy_fvs_cases"]
    assert result["greedy_fvs_max_size_ratio"] > 1.0
    assert result["failures"] == []


def test_biological_recovery_separates_atlas_coverage_from_algorithm_failure():
    result = feedback_verification.verify_biological_recovery(main.db.conn)
    assert result["summary"]["fully_covered"] >= 6
    assert result["summary"]["recovery_rate_when_covered"] == 1.0
    clock = result["arabidopsis_clock_architecture"]
    assert clock["supported_arms"] >= 1
    assert not clock["closed_three_module_loop_recoverable"]


def test_pathological_topologies_are_bounded_and_report_truncation():
    result = feedback_verification.verify_robustness()
    assert result["all_bounded"]
    cases = {case["name"]: case for case in result["cases"]}
    assert cases["large-scc"]["truncation"]["search"]
    assert cases["dense-core"]["truncation"]["search"]
    assert cases["many-small-sccs"]["feedback_cores"] == 300
    assert cases["many-small-sccs"]["truncation"]["cores"]
    assert not any(cases["acyclic"]["truncation"].values())


def test_score_is_monotonic_but_not_a_calibrated_probability():
    def edge(confidence, evidence="measured", sources=None):
        return {
            "sign": "activation", "confidence": confidence,
            "sign_evidence": evidence, "sources": sources or [],
        }

    low = feedback_control._circuit_score([edge(0.6), edge(0.7)])[0]
    high = feedback_control._circuit_score([edge(0.8), edge(0.9)])[0]
    measured = feedback_control._circuit_score([edge(0.8), edge(0.9)])[0]
    perturbation = feedback_control._circuit_score(
        [edge(0.8, "perturbation"), edge(0.9, "perturbation")]
    )[0]
    sourced = feedback_control._circuit_score(
        [edge(0.8, sources=["a", "b"]), edge(0.9, sources=["a", "b"])]
    )[0]
    assert low < high
    assert perturbation < measured < sourced


def test_api_success_cache_latest_and_parameter_invalidation(monkeypatch, tmp_path):
    monkeypatch.setenv("GRN_FEEDBACK_DB", str(tmp_path / "feedback.sqlite3"))
    payload = {
        "species": "Arabidopsis", "max_cores": 1,
        "max_circuits": 2, "max_search_states": 1_000,
    }
    with TestClient(main.app) as client:
        first_response = client.post("/api/v1/network/feedback-control", json=payload)
        second_response = client.post("/api/v1/network/feedback-control", json=payload)
        latest_response = client.get("/api/v1/network/feedback-control/Arabidopsis/latest")
        changed_response = client.post(
            "/api/v1/network/feedback-control", json={**payload, "min_confidence": 0.7},
        )
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert latest_response.status_code == 200
    assert changed_response.status_code == 200
    first = first_response.json()
    second = second_response.json()
    latest = latest_response.json()
    changed = changed_response.json()
    assert first["storage"]["status"] == "stored"
    assert second["storage"]["status"] == "cached"
    assert latest["run_id"] == first["run_id"]
    assert changed["run_id"] != first["run_id"]


def test_graph_change_invalidates_cache_and_concurrent_store_is_consistent(tmp_path):
    nodes = list("ABC")
    edges = [("A", "B", "activation"), ("B", "A", "repression")]
    conn = feedback_verification.fixture_connection(nodes, edges)
    store = feedback_control.FeedbackStore(tmp_path / "feedback.sqlite3")
    first = feedback_control.analyze_and_store(conn, store, "verification")
    conn.execute("UPDATE interactions SET confidence = 0.8 WHERE source_id = 'A'")
    changed = feedback_control.analyze_feedback(conn, "verification")
    assert changed["run_id"] != first["run_id"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(store.save, changed) for _ in range(4)]
        for future in futures:
            future.result()
    with sqlite3.connect(store.path) as persisted:
        assert persisted.execute("PRAGMA foreign_key_check").fetchall() == []
        assert persisted.execute(
            "SELECT COUNT(*) FROM feedback_runs WHERE run_id = ?", (changed["run_id"],)
        ).fetchone()[0] == 1
