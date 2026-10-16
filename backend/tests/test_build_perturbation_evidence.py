import json
import sqlite3
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_perturbation_evidence  # noqa: E402
import build_regulatory_candidates  # noqa: E402
from external_evidence import ensure_schema as ensure_evidence_schema  # noqa: E402
from perturbation_evidence import ensure_schema as ensure_perturbation_schema  # noqa: E402


def fixture():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE genes (
            id TEXT PRIMARY KEY, symbol TEXT, name TEXT, species TEXT, is_tf INTEGER
        );
        CREATE TABLE interactions (
            source_id TEXT, target_id TEXT, regulation_type TEXT, confidence REAL,
            sources TEXT, pmids TEXT, sign TEXT, sign_evidence TEXT,
            PRIMARY KEY(source_id,target_id)
        );
        INSERT INTO genes VALUES
            ('A','A','A','test',1), ('B','B','B','test',0),
            ('C','C','C','test',0), ('D','D','D','test',0), ('E','E','E','test',0);
    """)
    ensure_evidence_schema(conn)
    ensure_perturbation_schema(conn)
    conn.executescript("""
        CREATE TABLE perturbation_sign_calibration (
            species TEXT, relation_type TEXT, gate_pass INTEGER
        );
        INSERT INTO perturbation_sign_calibration VALUES ('test','activation',1);
    """)
    conn.execute(
        "INSERT INTO regulatory_evidence "
        "(species,source_id,target_id,relation_type,evidence_layer,directness,"
        "source_name,source_version,record_key,confidence,imported_at) "
        "VALUES ('test','A','B','regulation','direct_unsigned','binding',"
        "'binding','1','A-B',0.8,datetime('now'))"
    )
    rows = [
        ("test", "A", "knockdown", "B", -2.0, 1, "loss", json.dumps({"sample_id": "L1"})),
        ("test", "A", "induction", "C", 1.5, 1, "gain", json.dumps({"experiment": "G1"})),
        ("test", "A", "induction", "C", 2.0, 1, "gain", json.dumps({"experiment": "G2"})),
        ("test", "A", "induction", "D", 2.0, 1, "gain", json.dumps({"experiment": "G1"})),
        ("test", "A", "induction", "D", -2.0, 1, "gain", json.dumps({"experiment": "G2"})),
        ("test", "A", "induction", "E", 2.0, 1, "gain", json.dumps({"experiment": "G1"})),
    ]
    conn.executemany(
        "INSERT INTO perturbation_observations "
        "(species,perturbed_gene,perturbation_type,affected_gene,observed_log2fc,"
        "observed_significant,dataset_label,metadata) VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    return conn


def test_consensus_emits_binding_supported_and_replicated_pairs():
    conn = fixture()
    summary = build_perturbation_evidence.build(conn)
    assert summary["accepted_with_binding"] == 1
    assert summary["accepted_replicated_only"] == 1
    assert summary["sign_conflict"] == 1
    assert summary["unreplicated_perturbation_only"] == 1
    accepted = conn.execute(
        "SELECT target_id,relation_type,status FROM perturbation_sign_consensus "
        "WHERE status='accepted' ORDER BY target_id"
    ).fetchall()
    assert [tuple(row) for row in accepted] == [
        ("B", "activation", "accepted"), ("C", "activation", "accepted"),
    ]
    assert conn.execute(
        "SELECT status FROM perturbation_sign_consensus WHERE target_id='D'"
    ).fetchone()[0] == "sign_conflict"
    assert conn.execute(
        "SELECT COUNT(*) FROM regulatory_evidence "
        "WHERE source_name='Perturbation sign consensus'"
    ).fetchone()[0] == 2


def test_candidate_builder_uses_consensus_instead_of_conflicting_raw_experiments():
    conn = fixture()
    conn.executemany(
        "INSERT INTO regulatory_evidence "
        "(species,source_id,target_id,relation_type,evidence_layer,directness,"
        "source_name,source_version,record_key,confidence,imported_at) "
        "VALUES ('test','A','B',?,'perturbation_signed','downstream',"
        "'raw perturbation','1',?,0.6,datetime('now'))",
        [("activation", "raw-up"), ("repression", "raw-down")],
    )
    build_perturbation_evidence.build(conn)
    build_regulatory_candidates.build(conn)
    row = conn.execute(
        "SELECT relation_type,support_class,evidence_tier,status "
        "FROM regulatory_edge_candidates WHERE source_id='A' AND target_id='B'"
    ).fetchone()
    assert tuple(row) == ("activation", "binding_plus_perturbation", "supported", "candidate")
