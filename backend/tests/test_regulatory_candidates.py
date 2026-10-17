import sqlite3
import sys
from pathlib import Path

import feedback_control
from external_evidence import ensure_schema

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_regulatory_candidates  # noqa: E402
import candidate_impact


def fixture():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE genes (id TEXT PRIMARY KEY, symbol TEXT, name TEXT, species TEXT, is_tf INTEGER);
        CREATE TABLE interactions (
            source_id TEXT, target_id TEXT, regulation_type TEXT, confidence REAL,
            sources TEXT, pmids TEXT, sign TEXT, sign_evidence TEXT,
            PRIMARY KEY(source_id,target_id)
        );
        INSERT INTO genes VALUES ('A','A','A','test',1),('B','B','B','test',1),('C','C','C','test',1);
        INSERT INTO interactions VALUES ('A','B','activation',0.8,'[]','[]','activation','measured');
    """)
    ensure_schema(conn)
    conn.executescript("""
        CREATE TABLE perturbation_sign_calibration (
            species TEXT, relation_type TEXT, gate_pass INTEGER
        );
        INSERT INTO perturbation_sign_calibration VALUES ('test','activation',1);
    """)
    rows = [
        ("test", "B", "A", "repression", "direct_signed", "direct", "curated", "1", "b-a", 0.8),
        ("test", "B", "C", "regulation", "direct_unsigned", "binding", "chip", "1", "b-c-bind", 0.7),
        ("test", "B", "C", "activation", "perturbation_signed", "downstream", "perturb", "1", "b-c-perturb", 0.7),
        ("test", "C", "A", "repression", "direct_signed", "putative_direct", "unconfirmed", "1", "c-a", 0.4),
    ]
    conn.executemany(
        "INSERT INTO regulatory_evidence (species,source_id,target_id,relation_type,evidence_layer,directness,source_name,source_version,record_key,confidence,imported_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))", rows,
    )
    return conn


def test_candidate_policy_and_feedback_opt_in():
    conn = fixture()
    summary = build_regulatory_candidates.build(conn)
    assert summary["candidate"] == 3
    assert conn.execute(
        "SELECT support_class FROM regulatory_edge_candidates WHERE source_id='B' AND target_id='C'"
    ).fetchone()[0] == "binding_plus_perturbation"
    assert conn.execute(
        "SELECT evidence_tier FROM regulatory_edge_candidates WHERE source_id='C' AND target_id='A'"
    ).fetchone()[0] == "exploratory"

    observed = feedback_control.analyze_feedback(conn, "test")
    completed = feedback_control.analyze_feedback(
        conn, "test", feedback_control.FeedbackParameters(include_candidates=True),
    )
    assert observed["summary"]["feedback_cores"] == 0
    assert completed["summary"]["feedback_cores"] == 1
    assert completed["graph"]["includes_evidence_candidates"] is True
    assert any(
        edge["sign_evidence"] == "candidate"
        for system in completed["systems"] for edge in system["edges"]
    )

    exploratory = feedback_control.analyze_feedback(
        conn, "test", feedback_control.FeedbackParameters(
            include_candidates=True, include_exploratory=True, min_confidence=0.4,
        ),
    )
    assert exploratory["graph"]["includes_exploratory_candidates"] is True


def test_feedback_can_isolate_cross_species_transfer_assumptions():
    conn = fixture()
    build_regulatory_candidates.build(conn)
    conn.execute(
        "UPDATE regulatory_edge_candidates SET evidence_sources='[\"local evidence\"]'"
    )
    conn.execute(
        "UPDATE regulatory_edge_candidates SET evidence_sources='[\"Conserved signed orthology\"]' "
        "WHERE source_id='C' AND target_id='A'"
    )
    conn.execute(
        "UPDATE regulatory_edge_candidates SET evidence_tier='exploratory' "
        "WHERE source_id='B' AND target_id='C'"
    )

    result = feedback_control.analyze_feedback(
        conn, "test", feedback_control.FeedbackParameters(
            include_candidates=True,
            include_exploratory=True,
            candidate_scope="cross_species_transfer",
            min_confidence=0.4,
        ),
    )

    assert result["parameters"]["candidate_scope"] == "cross_species_transfer"
    assert result["graph"]["candidate_scope"] == "cross_species_transfer"
    assert result["evidence_completion"]["candidate_edges"] == 2
    assert result["graph"]["candidate_edges_admitted"] == 2
    assert result["graph"]["exploratory_edges_admitted"] == 1


def test_cycle_closing_candidates_are_ranked_by_marginal_impact():
    conn = fixture()
    build_regulatory_candidates.build(conn)
    summary = candidate_impact.rank_candidates(conn, "test")["test"]
    ranked = candidate_impact.top_impacts(conn, "test")
    assert summary["cycle_closing"] >= 1
    assert ranked[0]["closes_cycle"] is True
    assert ranked[0]["feedback_nodes_added"] >= 1


def test_supported_evidence_completes_existing_unsigned_pair_as_candidate():
    conn = fixture()
    conn.execute(
        "INSERT INTO interactions VALUES "
        "('B','C','regulation',0.7,'[]','[]',NULL,'unknown')"
    )
    build_regulatory_candidates.build(conn)
    assert conn.execute(
        "SELECT status,support_class FROM regulatory_edge_candidates "
        "WHERE source_id='B' AND target_id='C'"
    ).fetchone() == ("candidate", "binding_plus_perturbation")


def test_cross_species_transfer_requires_calibration_and_recipient_support():
    conn = fixture()
    conn.execute(
        "INSERT INTO regulatory_evidence (species,source_id,target_id,relation_type,evidence_layer,"
        "directness,source_name,source_version,record_key,confidence,imported_at) "
        "VALUES ('test','A','C','activation','orthology_transferred','conserved',"
        "'Conserved signed orthology','v2','transfer',.7,datetime('now'))"
    )
    conn.executescript("""
        CREATE TABLE cross_species_transfer_calibration (
            species TEXT, relation_type TEXT, mapping_class TEXT, gate_pass INTEGER
        );
        INSERT INTO cross_species_transfer_calibration VALUES
            ('test','activation','explicit_one_to_one',1);
        CREATE TABLE orthology_transfer_candidates (
            species TEXT,source_id TEXT,target_id TEXT,relation_type TEXT,mapping_class TEXT,
            mapping_score REAL,donor_species TEXT,donor_sources TEXT,
            recipient_binding_sources TEXT,recipient_cis_support INTEGER,
            source_independent INTEGER,edge_score REAL,sign_score REAL,status TEXT
        );
        INSERT INTO orthology_transfer_candidates VALUES
            ('test','A','C','activation','explicit_one_to_one',.9,'["donor"]','["curated"]',
             '["binding"]',0,1,.8,.85,'qualified');
    """)
    build_regulatory_candidates.build(conn)
    assert conn.execute(
        "SELECT support_class,evidence_tier FROM regulatory_edge_candidates "
        "WHERE source_id='A' AND target_id='C'"
    ).fetchone() == ("supported_cross_species_transfer", "supported")
