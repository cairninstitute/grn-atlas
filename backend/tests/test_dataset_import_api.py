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
            ("TF1", "TP53", "tumor protein p53", "human", 1, "protein_coding", "P53", None),
            ("TG1", "BAX", "BCL2 associated X", "human", 0, "protein_coding", None, None),
            ("TG2", "MDM2", "MDM2 proto-oncogene", "human", 0, "protein_coding", None, None),
            ("AT1", "ABF1", "ABRE binding factor 1", "arabidopsis", 1, "protein_coding", "AT1G49720", None),
        ],
    )
    db.executemany(
        "INSERT INTO interactions (source_id,target_id,regulation_type,confidence,sources,pmids) VALUES (?,?,?,?,?,?)",
        [
            ("TF1", "TG1", "activation", 0.9, '["TRRUST"]', '["12345"]'),
            ("TF1", "TG2", "repression", 0.85, '["TRRUST"]', '["45678"]'),
        ],
    )
    db.executemany("INSERT INTO go_terms (go_id,name,namespace) VALUES (?,?,?)", [
        ("GO:1", "apoptotic process", "BP"),
        ("GO:2", "stress response", "BP"),
    ])
    db.executemany("INSERT INTO go_annotations (gene_id,go_id) VALUES (?,?)", [
        ("TG1", "GO:1"), ("TG2", "GO:1"), ("TF1", "GO:2"),
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


def test_dataset_import_plain_list_maps_and_reports_unmapped(client):
    payload = {"content": "TP53\nBAX\nNOPE\n", "species": "human"}
    r = client.post("/api/v1/datasets/import", json=payload).json()
    assert r["dataset_type"] == "plain_gene_list"
    assert r["mapped_gene_ids"] == ["TF1", "TG1"]
    assert r["unmapped_count"] == 1
    assert r["species_guess"] == "human"


def test_dataset_import_plain_list_accepts_comma_and_semicolon_separators(client):
    payload = {"content": "TP53,BAX;MDM2", "species": "human"}
    r = client.post("/api/v1/datasets/import", json=payload).json()
    assert r["dataset_type"] == "plain_gene_list"
    assert r["mapped_gene_ids"] == ["TF1", "TG1", "TG2"]
    assert r["unmapped_count"] == 0


def test_dataset_import_tabular_detects_columns_and_scores(client):
    payload = {"content": "gene_symbol,score\nTP53,2.1\nMDM2,1.2\n", "species": "human", "filename": "hits.csv"}
    r = client.post("/api/v1/datasets/import", json=payload).json()
    assert r["dataset_type"] == "tabular_gene_set_with_scores"
    assert r["gene_column"] == "gene_symbol"
    assert r["score_column"] == "score"
    assert r["mapped_gene_ids"] == ["TF1", "TG2"]
    assert r["filename"] == "hits.csv"


def test_dataset_import_normalizes_species_text(client):
    payload = {"content": "TP53\nBAX\n", "species": " Human "}
    r = client.post("/api/v1/datasets/import", json=payload).json()
    assert r["species_filter"] == "human"
    assert r["species_guess"] == "human"
    assert r["mapped_gene_ids"] == ["TF1", "TG1"]


def test_user_gene_set_analysis_runs_first_pass_workflow(client):
    payload = {"content": "TP53\nBAX\nMDM2\n", "species": "human", "intent": "network"}
    r = client.post("/api/v1/user/gene-set/analyze", json=payload).json()
    assert r["species"] == "human"
    assert r["analyzed_gene_count"] == 3
    assert r["candidate_triage"]["ranked_candidates"][0]["gene_id"] == "TF1"
    assert r["upstream_regulators"]["regulators"][0]["gene_id"] == "TF1"
    assert "subgraph" in r and len(r["subgraph"]["nodes"]) == 3


def test_user_gene_set_analysis_normalizes_species_text(client):
    payload = {"content": "TP53\nBAX\nMDM2\n", "species": " HUMAN ", "intent": "network"}
    r = client.post("/api/v1/user/gene-set/analyze", json=payload).json()
    assert r["species"] == "human"
    assert r["analyzed_gene_count"] == 3
