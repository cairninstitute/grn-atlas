import asyncio
import sqlite3
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import feedback_control  # noqa: E402


def _fixture_connection():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE genes (
            id TEXT PRIMARY KEY, symbol TEXT, name TEXT, species TEXT,
            is_tf INTEGER, gene_type TEXT, synonyms TEXT, symbol_source TEXT
        );
        CREATE TABLE interactions (
            source_id TEXT, target_id TEXT, regulation_type TEXT, confidence REAL,
            sources TEXT, pmids TEXT, sign TEXT, sign_evidence TEXT, sign_r REAL,
            PRIMARY KEY (source_id, target_id)
        );
    """)
    genes = [(gene, gene, gene, "test", 1, "protein_coding", None, None)
             for gene in "ABCDEFGH"]
    conn.executemany("INSERT INTO genes VALUES (?,?,?,?,?,?,?,?)", genes)
    edges = [
        ("A", "B", "repression"), ("B", "A", "repression"),
        ("C", "D", "repression"), ("D", "E", "repression"),
        ("E", "C", "repression"), ("F", "F", "activation"),
        ("G", "H", "activation"),
    ]
    conn.executemany(
        "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?,?)",
        [(source, target, sign, 0.9, '["fixture"]', '[]', sign, "measured", None)
         for source, target, sign in edges],
    )
    return conn


def test_feedback_analysis_finds_and_classifies_control_structures():
    result = feedback_control.analyze_feedback(_fixture_connection(), "test")
    circuits = [circuit for core in result["cores"] for circuit in core["circuits"]]
    families = {circuit["family"] for circuit in circuits}
    assert result["summary"]["feedback_cores"] == 3
    assert result["summary"]["feedback_genes"] == 6
    assert {"mutual_repression", "repressilator", "positive_autoregulation"} <= families
    assert all(circuit["confidence_label"] == "high" for circuit in circuits)
    assert all(core["controller_analysis"]["breaks_all_detected_feedback"] for core in result["cores"])


def test_feedback_analysis_excludes_unsigned_and_acyclic_edges():
    conn = _fixture_connection()
    conn.execute(
        "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?,?)",
        ("H", "G", "regulation", 0.99, '[]', '[]', None, "unknown", None),
    )
    result = feedback_control.analyze_feedback(conn, "test")
    assert result["graph"]["edges"] == 7
    assert all(
        gene["id"] not in {"G", "H"}
        for core in result["cores"] for gene in core["gene_sample"]
    )


def test_feedback_analysis_reports_species_gene_count_when_no_signed_edges():
    conn = _fixture_connection()
    conn.execute("DELETE FROM interactions")
    result = feedback_control.analyze_feedback(conn, "test")
    assert result["graph"]["nodes"] == 8
    assert result["graph"]["edges"] == 0
    assert result["summary"]["feedback_cores"] == 0
    assert result["evidence_boundary"].startswith("No signed edges")


def test_feedback_analysis_discovers_annotation_supported_control_system():
    conn = _fixture_connection()
    conn.executemany(
        "INSERT INTO genes VALUES (?,?,?,?,?,?,?,?)",
        [(f"X{index}", f"X{index}", f"X{index}", "test", 0, "protein_coding", None, None)
         for index in range(20)],
    )
    conn.execute(
        "UPDATE interactions SET regulation_type='activation', sign='activation' "
        "WHERE source_id='B' AND target_id='A'"
    )
    conn.executemany(
        "INSERT INTO genes VALUES (?,?,?,?,?,?,?,?)",
        [("OA", "OA", "Ortholog A", "other", 1, "protein_coding", None, None),
         ("OB", "OB", "Ortholog B", "other", 1, "protein_coding", None, None)],
    )
    conn.execute(
        "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?,?)",
        ("OA", "OB", "repression", 0.9, '["fixture"]', '[]', "repression", "measured", None),
    )
    conn.executescript("""
        CREATE TABLE go_terms (go_id TEXT PRIMARY KEY, name TEXT, namespace TEXT);
        CREATE TABLE go_annotations (gene_id TEXT, go_id TEXT);
        CREATE TABLE pathways (pathway_id TEXT PRIMARY KEY, name TEXT, source TEXT);
        CREATE TABLE pathway_annotations (gene_id TEXT, pathway_id TEXT);
        CREATE TABLE cis_support_edges (
            source_id TEXT, target_id TEXT, peak_id TEXT, support_type TEXT,
            score REAL, species TEXT
        );
        CREATE TABLE perturbation_observations (
            species TEXT, perturbed_gene TEXT, perturbation_type TEXT,
            affected_gene TEXT, observed_log2fc REAL, observed_significant INTEGER,
            dataset_label TEXT, metadata TEXT
        );
        CREATE TABLE edge_tissue_weights (
            source_id TEXT, target_id TEXT, tissue TEXT, coexpression REAL, species TEXT
        );
        CREATE TABLE orthologs (
            gene_a TEXT, gene_b TEXT, species_a TEXT, species_b TEXT,
            rel_type TEXT, score REAL
        );
        INSERT INTO go_terms VALUES ('GO:CLOCK', 'circadian rhythm', 'biological_process');
        INSERT INTO go_annotations VALUES ('A', 'GO:CLOCK'), ('B', 'GO:CLOCK'), ('C', 'GO:CLOCK');
        INSERT INTO cis_support_edges VALUES ('A', 'B', 'peak-1', 'motif_in_peak', 0.9, 'test');
        INSERT INTO perturbation_observations VALUES
            ('test', 'A', 'knockout', 'B', -1.2, 1, 'fixture', '{}');
        INSERT INTO edge_tissue_weights VALUES
            ('A', 'B', 'seedling', 0.8, 'test'), ('B', 'A', 'seedling', -0.7, 'test');
        INSERT INTO orthologs VALUES
            ('A', 'OA', 'test', 'other', 'one2one', 1.0),
            ('B', 'OB', 'test', 'other', 'one2one', 1.0);
    """)
    result = feedback_control.analyze_feedback(conn, "test")
    system = next(system for system in result["systems"] if system["name"] == "circadian rhythm")
    assert system["architecture"] == "oscillator_scaffold"
    assert system["completeness"] == "partial_architecture"
    assert system["discovery_mode"] == "annotation_supported"
    assert system["context_support"]["cis_supported_edges"] == 1
    assert system["context_support"]["perturbation_supported_edges"] == 1
    assert system["context_support"]["conservation"]["conserved_signed_edges"] == 1
    assert result["summary"]["biological_systems"] >= 1


def test_feedback_search_budget_is_explicit():
    conn = _fixture_connection()
    result = feedback_control.analyze_feedback(
        conn, "test", feedback_control.FeedbackParameters(
            max_search_states=1_000, circuits_per_core=1, max_circuits=1,
        ),
    )
    assert result["summary"]["circuits_returned"] == 1
    assert result["truncation"]["cores"] or result["truncation"]["circuits"]


def test_feedback_store_normalizes_results_and_reuses_cache(tmp_path):
    conn = _fixture_connection()
    store = feedback_control.FeedbackStore(tmp_path / "feedback.sqlite3")
    first = feedback_control.analyze_and_store(conn, store, "test")
    second = feedback_control.analyze_and_store(conn, store, "test")
    assert first["storage"]["status"] == "stored"
    assert second["storage"]["status"] == "cached"
    assert second["run_id"] == first["run_id"]
    with sqlite3.connect(store.path) as stored:
        assert stored.execute("SELECT COUNT(*) FROM feedback_runs").fetchone()[0] == 1
        assert stored.execute("SELECT COUNT(*) FROM feedback_cores").fetchone()[0] == 3
        assert stored.execute("SELECT COUNT(*) FROM feedback_core_genes").fetchone()[0] == 6
        assert stored.execute("SELECT COUNT(*) FROM feedback_circuits").fetchone()[0] >= 3
        assert stored.execute("SELECT COUNT(*) FROM feedback_circuit_edges").fetchone()[0] >= 6


def test_real_api_rejects_unknown_species(monkeypatch, tmp_path):
    import main

    monkeypatch.setenv("GRN_FEEDBACK_DB", str(tmp_path / "feedback.sqlite3"))
    request = main.FeedbackControlRequest(species="definitely-not-a-species")
    try:
        asyncio.run(main.feedback_control_analysis(request))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("unknown species should be rejected")
