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
    db.execute("INSERT INTO genes (id,symbol,name,species,is_tf,gene_type,synonyms,symbol_source) VALUES (?,?,?,?,?,?,?,?)",
               ("TF1", "TF1", "human TF one", "human", 1, "protein_coding", None, None))
    db.execute("INSERT INTO interactions (source_id,target_id,regulation_type,confidence,sources,pmids) VALUES (?,?,?,?,?,?)",
               ("TF1", "TF1", "activation", 0.9, '["TRRUST"]', '["12345"]'))
    db.execute("INSERT INTO orthologs VALUES (?,?,?,?,?,?)", ("TF1", "AT1", "human", "arabidopsis", "ortholog", 0.8))
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


def test_experiment_prioritize_returns_network_plan(client):
    r = client.post("/api/v1/experiments/prioritize", json={"gene_ids": ["TF1"], "intent": "experiment"}).json()
    assert r["plans"][0]["gene_id"] == "TF1"
    assert any(item["experiment"] == "network_perturbation" for item in r["plans"][0]["recommended_experiments"])
