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
    db.executemany("INSERT INTO genes (id,symbol,name,species,is_tf,gene_type,synonyms,symbol_source) VALUES (?,?,?,?,?,?,?,?)", [
        ("H1", "TP53", "human gene", "human", 1, "protein_coding", None, None),
        ("A1", "HY5", "arabidopsis gene", "arabidopsis", 1, "protein_coding", None, None),
    ])
    db.execute("INSERT INTO interactions VALUES (?,?,?,?,?,?)", ("H1", "H1", "activation", 0.9, '["TRRUST"]', '[]'))
    db.execute("INSERT INTO pathway_annotations VALUES (?,?)", ("H1", "P1"))
    db.execute("INSERT INTO trait_associations (gene_id,trait,pubmed_id,source) VALUES (?,?,?,?)", ("H1", "Trait A", "111", "GWAS Catalog"))
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "fixture.sqlite3"
    _build_fixture(path)
    os.environ["GRN_DB"] = str(path)
    import main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c
    os.environ.pop("GRN_DB", None)


def test_human_network_ready(client):
    r = client.get("/api/v1/coverage/report?species=human&intent=network").json()
    assert r["readiness_score"] > 0
    assert r["recommended_skills"]


def test_arabidopsis_traits_gap(client):
    r = client.get("/api/v1/coverage/report?species=arabidopsis&intent=traits").json()
    assert any(x["layer"] == "trait_associations" for x in r["coverage_gaps"])


def test_unknown_intent(client):
    r = client.get("/api/v1/coverage/report?species=human&intent=unknown").json()
    assert r["readiness_score"] == 0.0
