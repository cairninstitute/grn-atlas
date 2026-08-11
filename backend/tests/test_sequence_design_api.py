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
    db.execute("INSERT INTO motifs (motif_id,source,jaspar_id,tf_gene_id,tf_symbol) VALUES (?,?,?,?,?)",
               ("M1|TF1", "JASPAR2024", "MA1", "TF1", "TF1"))
    db.execute("INSERT INTO gene_id_crosswalk VALUES ('human','TG1','TG1.1','GRCh38','1:1')")
    db.execute("INSERT INTO gene_windows VALUES ('TG1.1','GRCh38','promoter','1',90,140,1)")
    db.execute("INSERT INTO motif_hits VALUES ('TG1.1','M1|TF1','GRCh38','promoter','1',100,110,1,10.0,1e-6,'JASPAR_scan',0.9)")
    db.execute("INSERT INTO interactions (source_id,target_id,regulation_type,confidence,sources,pmids) VALUES (?,?,?,?,?,?)",
               ("TF1", "TG1", "activation", 0.9, '["TRRUST"]', '["12345"]'))
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


def test_variant_effect_finds_overlapping_site(client):
    r = client.post("/api/v1/variants/effect", json={"gene_id": "TG1", "position": 105, "assembly": "GRCh38"}).json()
    assert r["results"][0]["tf_gene_id"] == "TF1"
    assert r["results"][0]["predicted_effect"] == "site_overlap_candidate"


def test_promoter_edit_prioritization_returns_site(client):
    r = client.post("/api/v1/promoter/edit-prioritize", json={"gene_id": "TG1"}).json()
    assert r["results"][0]["tf_gene_id"] == "TF1"


def test_crispr_design_returns_guides(client):
    seq = "AAAACCCCGGGGTTTTAAAACCCCGGGGTTTTAAAAGG"
    r = client.post("/api/v1/crispr/design", json={"sequence": seq}).json()
    assert r["guides"]


def test_primer_design_returns_pairs(client):
    seq = "ATGCGTACGTAGCTAGCTAGCTAGCTAGGCTAGCTAGCTAGCTAACGATCGATCGTAGCTAGCTAGCTAGCTAGCTAGCTA"
    r = client.post("/api/v1/primers/design", json={"sequence": seq, "product_min": 40, "product_max": 80}).json()
    assert r["primer_pairs"]
