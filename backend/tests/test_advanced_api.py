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
        ("TF1", "TG2", "repression", 0.7, '["TRRUST"]', '[]'),
    ])
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


def test_celltype_regulation_reports_blocked(client):
    r = client.post("/api/v1/celltype/regulation", json={"species": "human"}).json()
    assert r["supported"] is False
    assert "single-cell" in r["reason"].lower()


def test_trajectory_regulation_reports_blocked(client):
    r = client.post("/api/v1/trajectory/regulation", json={"species": "human"}).json()
    assert r["supported"] is False
    assert "trajectory" in r["reason"].lower()


def test_combinatorial_perturbation_returns_ranked_combo(client):
    r = client.post("/api/v1/perturb/combinatorial", json={"gene_ids": ["TF1", "TG1"], "combo_size": 2}).json()
    assert r["ranked_combinations"]
    assert len(r["ranked_combinations"][0]["combo"]) == 2


def test_species_onboarding_plan_returns_staged_plan(client):
    r = client.post("/api/v1/species/onboarding-plan", json={"species_name": "wheat", "intended_capabilities": ["expression", "orthology"]}).json()
    assert r["species_name"] == "wheat"
    assert r["staged_plan"]
