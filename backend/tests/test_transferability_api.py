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
        ("H1", "H1", "Human one", "human", 1, "protein_coding", None, None),
        ("H2", "H2", "Human two", "human", 0, "protein_coding", None, None),
        ("M1", "M1", "Mouse one", "mouse", 1, "protein_coding", None, None),
    ])
    db.executemany("INSERT INTO interactions (source_id,target_id,regulation_type,confidence,sources,pmids) VALUES (?,?,?,?,?,?)", [
        ("H1", "H2", "activation", 0.9, '["TRRUST"]', '["12345"]'),
        ("M1", "M1", "activation", 0.7, '["TRRUST"]', '[]'),
    ])
    db.execute("INSERT INTO orthologs (gene_a,gene_b,species_a,species_b,rel_type,score) VALUES (?,?,?,?,?,?)",
               ("H1", "M1", "human", "mouse", "1:1", 0.95))
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


def test_transferability_returns_ortholog_profile(client):
    r = client.post("/api/v1/research/transferability", json={"gene_id": "H1", "target_species": "mouse", "intent": "network"}).json()
    assert r["best_target_ortholog"]["gene_id"] == "M1"
    assert r["supported_transfer_claims"]
