import json
import sqlite3

import provenance
from scripts.audit_provenance_manifest import audit


def test_manifest_source_labels_are_unique():
    labels = [label for source in provenance.SOURCES for label in source.get("source_labels", [])]
    assert len(labels) == len(set(labels))


def test_manifest_covers_built_database_sources():
    with sqlite3.connect(provenance.__file__.replace("provenance.py", "data/grn.sqlite3")) as conn:
        result = audit(conn)
    assert result["unmapped"] == []


def test_audit_detects_unknown_source():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE interactions (sources TEXT)")
    conn.execute("INSERT INTO interactions VALUES (?)", (json.dumps(["UnknownDB"]),))
    assert audit(conn)["unmapped"] == ["UnknownDB"]
