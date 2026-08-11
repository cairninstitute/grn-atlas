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
        ("TF1", "TF1", "human TF one", "human", 1, "protein_coding", None, None),
        ("TG1", "TG1", "human target one", "human", 0, "protein_coding", None, None),
        ("TG2", "TG2", "human target two", "human", 0, "protein_coding", None, None),
    ])
    db.executemany("INSERT INTO interactions (source_id,target_id,regulation_type,confidence,sources,pmids) VALUES (?,?,?,?,?,?)", [
        ("TF1", "TG1", "activation", 0.9, '["TRRUST"]', '["12345"]'),
        ("TF1", "TG2", "activation", 0.7, '["TRRUST"]', '[]'),
    ])
    db.execute("INSERT INTO trait_associations (gene_id,trait,pubmed_id,source) VALUES (?,?,?,?)",
               ("TF1", "Trait A", "111", "GWAS Catalog"))
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


def test_consensus_ranking_returns_ranked_candidates(client):
    r = client.post("/api/v1/research/consensus-ranking", json={"gene_ids": ["TF1", "TG1", "TG2"]}).json()
    assert r["ranked_candidates"][0]["gene_id"] == "TF1"
    assert "consensus_score" in r["ranked_candidates"][0]


def test_counterfactual_analysis_reports_overturn_conditions(client):
    r = client.post("/api/v1/research/counterfactual-analysis", json={"gene_ids": ["TF1", "TG1"]}).json()
    assert r["winner"]["gene_id"] == "TF1"
    assert r["overturn_conditions"]
