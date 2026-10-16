import json
import sqlite3

from scripts import promote_evidence_to_interactions as promotion


def _database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE interactions (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            regulation_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            sources TEXT NOT NULL,
            pmids TEXT NOT NULL DEFAULT '[]',
            sign TEXT,
            sign_evidence TEXT,
            PRIMARY KEY (source_id, target_id)
        );
        CREATE TABLE regulatory_evidence (
            source_name TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT,
            confidence REAL
        );
        """
    )
    return conn


def _evidence(conn, source, regulator, target, relation="regulation", confidence=0.8):
    conn.execute(
        "INSERT INTO regulatory_evidence VALUES (?, ?, ?, ?, ?)",
        (source, regulator, target, relation, confidence),
    )


def test_promotion_repairs_existing_rows_and_handles_conflicting_signs():
    conn = _database()
    conn.executemany(
        "INSERT INTO interactions VALUES (?, ?, ?, ?, ?, '[]', ?, ?)",
        [
            ("A", "B", "activation", 0.7, '["CollecTRI"]', None, None),
            ("C", "D", "regulation", 0.6, '["TFLink"]', None, None),
            ("G", "H", "activation", 0.8, '["curated"]', "activation", "measured"),
        ],
    )
    _evidence(conn, "CollecTRI", "A", "B", "activation")
    _evidence(conn, "TFLink small-scale", "C", "D")
    _evidence(conn, "CollecTRI", "E", "F", "activation")
    _evidence(conn, "SIGNOR", "E", "F", "repression")
    _evidence(conn, "SIGNOR", "G", "H", "repression")
    _evidence(conn, "ChIP-Atlas", "I", "J")

    stats = promotion.promote(conn)

    assert conn.execute(
        "SELECT regulation_type, sign, sign_evidence FROM interactions "
        "WHERE source_id='A' AND target_id='B'"
    ).fetchone() == ("activation", "activation", "measured")
    sources, sign_evidence = conn.execute(
        "SELECT sources, sign_evidence FROM interactions "
        "WHERE source_id='C' AND target_id='D'"
    ).fetchone()
    assert json.loads(sources) == ["TFLink small-scale"]
    assert sign_evidence == "unknown"
    assert conn.execute(
        "SELECT regulation_type, sign, sign_evidence FROM interactions "
        "WHERE source_id='E' AND target_id='F'"
    ).fetchone() == ("regulation", None, "unknown")
    assert conn.execute(
        "SELECT regulation_type, sign, sign_evidence FROM interactions "
        "WHERE source_id='G' AND target_id='H'"
    ).fetchone() == ("activation", "activation", "measured")
    assert conn.execute(
        "SELECT sign_evidence FROM interactions WHERE source_id='I' AND target_id='J'"
    ).fetchone()[0] == "unknown"
    assert stats["conflicted_pairs"] == 1
    assert stats["signs_repaired"] == 1
    assert stats["source_labels_normalized"] == 1

    second = promotion.promote(conn)
    assert second["new_edges"] == 0
    assert second["updated_edges"] == 0
    assert second["null_sign_evidence_repaired"] == 0
