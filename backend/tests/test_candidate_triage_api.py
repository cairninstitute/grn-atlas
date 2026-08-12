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
    ])
    db.executemany("INSERT INTO interactions (source_id,target_id,regulation_type,confidence,sources,pmids) VALUES (?,?,?,?,?,?)", [
        ("TF1", "TG1", "activation", 0.9, '["TRRUST"]', '["12345"]'),
        ("TF1", "TF1", "activation", 0.6, '["TRRUST"]', '[]'),
    ])
    db.execute("INSERT INTO motifs (motif_id,source,jaspar_id,tf_gene_id,tf_symbol) VALUES (?,?,?,?,?)",
               ("M1|TF1", "JASPAR2024", "MA1", "TF1", "TF1"))
    db.execute("INSERT INTO gene_id_crosswalk VALUES ('human','TG1','TG1.1','GRCh38','1:1')")
    db.execute("INSERT INTO motif_hits VALUES ('TG1.1','M1|TF1','GRCh38','promoter','1',100,110,1,10.0,1e-6,'JASPAR_scan',0.9)")
    db.execute("INSERT INTO trait_associations (gene_id,trait,pubmed_id,source) VALUES (?,?,?,?)",
               ("TG1", "Trait A", "111", "GWAS Catalog"))
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


def test_candidate_triage_ranks_tf_first(client):
    r = client.post("/api/v1/candidates/triage", json={"gene_ids": ["TG1", "TF1"], "intent": "network"}).json()
    assert r["ranked_candidates"][0]["gene_id"] == "TF1"
    assert r["ranked_candidates"][0]["priority_score"] >= r["ranked_candidates"][1]["priority_score"]
    assert r["ranked_candidates"][0]["label"] == "TF1"
    assert r["ranked_candidates"][0]["label_inferred"] is False


def test_candidate_triage_tracks_missing(client):
    r = client.post("/api/v1/candidates/triage", json={"gene_ids": ["TF1", "NOPE"], "intent": "experiment"}).json()
    assert any(item["gene_id"] == "NOPE" for item in r["excluded_genes"])


def test_upstream_regulators_include_friendly_labels(client):
    r = client.post("/api/v1/upstream-regulators", json={"gene_ids": ["TG1"], "species": "human", "min_overlap": 1}).json()
    assert r["regulators"][0]["gene_id"] == "TF1"
    assert r["regulators"][0]["label"] == "TF1"
    assert r["regulators"][0]["label_inferred"] is False
