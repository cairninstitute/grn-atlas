import importlib
import os
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
import pytest


REAL_DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"
pytestmark = pytest.mark.skipif(not REAL_DB.exists(), reason="need built DB for schema")


def _build_fixture(path):
    src = sqlite3.connect(REAL_DB)
    schema = [r[0] for r in src.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")]
    src.close()
    db = sqlite3.connect(path)
    for stmt in schema:
        db.execute(stmt)
    db.executemany(
        "INSERT INTO genes (id,symbol,name,species,is_tf,gene_type,synonyms,symbol_source) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("GX", "GX", "gene x", "petunia", 1, "protein_coding", None, None),
            ("GY", "GY", "gene y", "petunia", 0, "protein_coding", None, None),
            ("GZ", "GZ", "gene z", "petunia", 0, "protein_coding", None, None),
            ("TP53", "TP53", "tumor protein 53", "human", 1, "protein_coding", None, None),
            ("BAX", "BAX", "BAX", "human", 0, "protein_coding", None, None),
        ],
    )
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "fixture.sqlite3"
    _build_fixture(path)
    os.environ["GRN_DB"] = str(path)
    import main
    importlib.reload(main)
    import expression
    expression._cache[str(expression.path_for("petunia"))] = expression.ExpressionMatrix({
        "meta": {"unit": "TPM"},
        "samples": [
            {"run": "r1", "tissue": "leaf"},
            {"run": "r2", "tissue": "leaf"},
            {"run": "r3", "tissue": "flower"},
            {"run": "r4", "tissue": "flower"},
        ],
        "genes": {
            "GX": [1.0, 2.0, 16.0, 32.0],
            "GY": [4.0, 4.0, 4.0, 4.0],
            "GZ": [20.0, 20.0, 2.0, 1.0],
        },
    })
    with TestClient(main.app) as c:
        yield c
    os.environ.pop("GRN_DB", None)


def test_atlas_differential_expression_contrast(client):
    r = client.post("/api/v1/expression/differential", json={
        "species": "petunia",
        "group_a": ["leaf"],
        "group_b": ["flower"],
        "top": 2,
    }).json()
    assert r["mode"] == "atlas_groups"
    assert r["species"] == "petunia"
    assert r["results"][0]["gene_id"] in {"GX", "GZ"}
    assert r["recommended_skills"] == ["grn-upstream", "grn-enrichment", "grn-candidate-triage"]
    assert "label" in r["results"][0]


def test_atlas_differential_expression_force_includes_requested_genes(client):
    r = client.post("/api/v1/expression/differential", json={
        "species": "petunia",
        "group_a": ["leaf"],
        "group_b": ["flower"],
        "top": 1,
        "gene_ids": ["GY"],
    }).json()
    assert r["results"][0]["gene_id"] != "GY"
    assert r["forced_results"][0]["gene_id"] == "GY"
    assert r["forced_results"][0]["label"] == "GY"


def test_imported_deg_table_maps_rows(client):
    content = "gene_symbol,log2fc,padj\nTP53,2.5,0.01\nBAX,-1.2,0.04\nNOPE,4.0,0.2\n"
    r = client.post("/api/v1/expression/differential", json={
        "content": content,
        "species": "human",
        "filename": "deg.csv",
    }).json()
    assert r["mode"] == "imported_table"
    assert r["mapped_count"] == 2
    assert r["results"][0]["gene_id"] == "TP53"
    assert r["warnings"]
