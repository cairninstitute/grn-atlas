import sqlite3

from external_evidence import (begin_import, benchmark_source, ensure_schema, finish_import,
                               gene_resolver, replace_source_evidence)


def fixture_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE genes (id TEXT PRIMARY KEY, symbol TEXT, species TEXT);
        CREATE TABLE gene_aliases (gene_id TEXT, alias TEXT);
        CREATE TABLE interactions (
            source_id TEXT, target_id TEXT, regulation_type TEXT,
            confidence REAL, sources TEXT, pmids TEXT
        );
        INSERT INTO genes VALUES ('TF1', 'TF1', 'human'), ('TG1', 'TG1', 'human'),
                                 ('TG2', 'TG2', 'human');
        INSERT INTO gene_aliases VALUES ('TF1', 'factor one');
        INSERT INTO interactions VALUES ('TF1', 'TG1', 'activation', .9, '["TRRUST"]', '[]');
    """)
    ensure_schema(conn)
    return conn


def test_gene_resolver_is_case_insensitive_and_handles_aliases():
    conn = fixture_db()
    resolve = gene_resolver(conn, "human")
    assert resolve("tf1") == "TF1"
    assert resolve("Factor One") == "TF1"
    assert resolve("missing") is None


def test_evidence_is_source_level_and_benchmarked_without_graph_mutation():
    conn = fixture_db()
    rows = [
        {"species": "human", "source_id": "TF1", "target_id": "TG1",
         "relation_type": "repression", "evidence_layer": "direct_signed",
         "record_key": "conflict"},
        {"species": "human", "source_id": "TF1", "target_id": "TG2",
         "relation_type": "activation", "evidence_layer": "direct_signed",
         "record_key": "new"},
    ]
    assert replace_source_evidence(conn, "Example", "1", 1, rows) == 2
    result = benchmark_source(conn, "Example")
    assert result["new_pairs"] == 1
    assert result["signed_conflicts"] == 1
    assert conn.execute("SELECT count(*) FROM interactions").fetchone()[0] == 1


def test_source_replacement_can_be_rolled_back():
    conn = fixture_db()
    original = [{
        "species": "human", "source_id": "TF1", "target_id": "TG1",
        "relation_type": "activation", "evidence_layer": "direct_signed",
        "record_key": "original",
    }]
    replace_source_evidence(conn, "Example", "1", None, original)
    conn.commit()
    conn.execute("SAVEPOINT replacement")
    replace_source_evidence(conn, "Example", "1", None, [{
        "species": "human", "source_id": "TF1", "target_id": "TG2",
        "relation_type": "repression", "evidence_layer": "direct_signed",
        "record_key": "replacement",
    }])
    conn.execute("ROLLBACK TO replacement")
    conn.execute("RELEASE replacement")
    assert conn.execute(
        "SELECT record_key FROM regulatory_evidence WHERE source_name='Example'"
    ).fetchall() == [("original",)]


def test_hashless_import_reuses_latest_run_without_leaving_running_duplicates():
    conn = fixture_db()
    first = begin_import(conn, "Example", "1", "https://example.test", None)
    finish_import(conn, first, {"stored": 1})
    second = begin_import(conn, "Example", "1", "https://example.test", None)
    finish_import(conn, second, {"stored": 2})
    assert second == first
    assert conn.execute(
        "SELECT status FROM source_import_runs WHERE import_run_id=?", (second,)
    ).fetchone()[0] == "complete"
