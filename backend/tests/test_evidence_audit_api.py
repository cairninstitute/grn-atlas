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
        ("ATTF", "HY5", "arabidopsis TF", "arabidopsis", 1, "protein_coding", None, None),
        ("ATTG", "CHS", "arabidopsis target", "arabidopsis", 0, "protein_coding", None, None),
    ])
    db.executemany("INSERT INTO interactions (source_id,target_id,regulation_type,confidence,sources,pmids) VALUES (?,?,?,?,?,?)", [
        ("TF1", "TG1", "activation", 0.9, '["TRRUST"]', '["12345"]'),
        ("ATTF", "ATTG", "activation", 0.7, '["Inferred:Arabidopsis"]', '[]'),
    ])
    db.execute("INSERT INTO inferred_edges (source_id,target_id,method,importance,species) VALUES (?,?,?,?,?)",
               ("TF1", "TG1", "GRNBoost2", 1.4, "human"))
    db.execute("INSERT INTO motifs (motif_id,source,jaspar_id,tf_gene_id,tf_symbol) VALUES (?,?,?,?,?)",
               ("M1|TF1", "JASPAR2024", "MA1", "TF1", "TF1"))
    db.execute("INSERT INTO gene_id_crosswalk VALUES ('human','TG1','TG1.1','GRCh38','1:1')")
    db.execute("INSERT INTO motif_hits VALUES ('TG1.1','M1|TF1','GRCh38','promoter','1',100,110,1,10.0,1e-6,'JASPAR_scan',0.9)")
    db.execute("INSERT INTO pathway_annotations VALUES (?,?)", ("TG1", "P1"))
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


def test_gene_audit(client):
    r = client.get("/api/v1/evidence/audit?scope=gene&gene_id=TG1").json()
    assert r["summary"]["supported"] is True
    assert r["evidence_summary"]["support_counts"]["pathway_supported"] >= 1
    assert r["evidence_summary"]["support_counts"]["trait_supported"] >= 1


def test_edge_audit(client):
    r = client.get("/api/v1/evidence/audit?scope=edge&source_id=TF1&target_id=TG1").json()
    assert r["evidence_summary"]["support_counts"]["curated"] == 1
    assert r["evidence_summary"]["support_counts"]["motif_supported"] >= 1


def test_edge_audit_missing_gene(client):
    r = client.get("/api/v1/evidence/audit?scope=edge&source_id=TF1&target_id=NOPE").json()
    assert r["confidence"]["label"] == "unsupported"
    assert r["coverage_gaps"]
