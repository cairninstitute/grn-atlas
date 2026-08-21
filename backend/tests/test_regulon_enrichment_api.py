"""Tests for the regulon enrichment endpoint."""
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def test_regulon_enrichment_basic():
    resp = client.post("/api/v1/regulon-enrichment", json={
        "gene_ids": ["TP53", "MDM2", "CDKN1A", "BAX", "BBC3", "GADD45A"],
        "species": "human",
        "top": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "regulators" in data
    assert data["species"] == "human"
    assert data["input_genes"] == 6


def test_regulon_enrichment_arabidopsis():
    resp = client.post("/api/v1/regulon-enrichment", json={
        "gene_ids": ["AT1G56650", "AT5G42910", "AT3G55120"],
        "species": "arabidopsis",
        "top": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["species"] == "arabidopsis"


def test_regulon_enrichment_too_few_genes():
    resp = client.post("/api/v1/regulon-enrichment", json={
        "gene_ids": ["TP53"],
        "species": "human",
    })
    assert resp.status_code == 200
