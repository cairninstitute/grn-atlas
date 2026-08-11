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
            ("TP53", "TP53", "tumor protein p53", "human", 1, "protein_coding", None, None),
            ("BAX", "BAX", "BAX", "human", 0, "protein_coding", None, None),
        ],
    )
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "fixture.sqlite3"
    _build_fixture(path)
    os.environ["GRN_DB"] = str(path)
    import main
    importlib.reload(main)
    import literature

    def fake_search(term, years_back=5, page_size=10):
        return [
            {
                "id": "1",
                "source": "MED",
                "title": "TP53 regulates BAX during apoptosis",
                "abstractText": "TP53 activates BAX and promotes apoptosis in response to damage.",
                "pmid": "12345",
                "doi": "10.1000/test",
                "journalTitle": "Journal A",
                "pubYear": "2025",
                "authorString": "A. Author",
            },
            {
                "id": "2",
                "source": "MED",
                "title": "BAX response is independent of TP53 in this model",
                "abstractText": "We found BAX induction independent of TP53 under these conditions.",
                "pmid": "67890",
                "doi": "10.1000/test2",
                "journalTitle": "Journal B",
                "pubYear": "2024",
                "authorString": "B. Author",
            },
        ]

    literature.search_europe_pmc = fake_search
    with TestClient(main.app) as c:
        yield c
    os.environ.pop("GRN_DB", None)


def test_literature_review_edge_classifies_results(client):
    r = client.get("/api/v1/literature/review?scope=edge&source_id=TP53&target_id=BAX&years_back=3").json()
    assert r["scope"] == "edge"
    assert r["summary"]["support"] >= 1
    assert r["summary"]["contradict"] >= 1
    assert "atlas_boundary" in r


def test_literature_review_gene_uses_gene_scope(client):
    r = client.get("/api/v1/literature/review?scope=gene&gene_id=TP53").json()
    assert r["gene"]["gene_id"] == "TP53"
    assert r["results"][0]["pmid"] == "12345"
