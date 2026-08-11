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


def test_experiment_optimizer_prefers_low_cost_options_under_constraints(client):
    r = client.post("/api/v1/experiments/optimize", json={
        "gene_ids": ["TF1"],
        "intent": "experiment",
        "budget_level": "low",
        "timeline_days": 1,
        "max_recommendations": 3,
    }).json()
    assert r["ranked_experiments"]
    top = r["ranked_experiments"][0]
    assert top["experiment"] in {"cross_species_conservation_check", "expression_context_review", "trait_association_followup"}
    assert "warnings" in r


def test_experiment_optimizer_respects_allowed_assays(client):
    r = client.post("/api/v1/experiments/optimize", json={
        "gene_ids": ["TF1"],
        "intent": "experiment",
        "allowed_assays": ["comparative"],
        "max_recommendations": 5,
    }).json()
    assert r["ranked_experiments"][0]["assay_class"] == "comparative"
