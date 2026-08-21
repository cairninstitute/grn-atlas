"""Tests for TF activity, pathway activity, and RNAi enhancement endpoints."""
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def test_tf_activity_ulm():
    resp = client.post("/api/v1/activity/tf", json={
        "gene_values": {"AT1G56650": 2.5, "AT5G42910": -1.2, "AT3G55120": 1.8,
                        "AT1G66390": -0.5, "AT5G07690": 3.1, "AT1G01060": -2.0},
        "species": "arabidopsis",
        "method": "ulm",
        "top": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["species"] == "arabidopsis"
    assert data["method"] == "ulm"
    assert "regulators" in data


def test_tf_activity_wmean():
    resp = client.post("/api/v1/activity/tf", json={
        "gene_values": {"TP53": 3.0, "MDM2": -2.0, "CDKN1A": 2.5,
                        "BAX": 1.8, "BCL2": -1.5, "GADD45A": 2.1},
        "species": "human",
        "method": "wmean",
        "top": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "wmean"


def test_tf_activity_tp53_rank_regression():
    gene_values = {"TP53": 3.0, "MDM2": -2.0, "CDKN1A": 2.5,
                   "BAX": 1.8, "BCL2": -1.5, "GADD45A": 2.1}
    for method in ("ulm", "wmean"):
        resp = client.post("/api/v1/activity/tf", json={
            "gene_values": gene_values,
            "species": "human",
            "method": method,
            "top": 10,
            "min_regulon_size": 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        top_symbols = [r["symbol"] for r in data["regulators"][:5]]
        assert "TP53" in top_symbols


def test_tf_activity_too_few_genes():
    resp = client.post("/api/v1/activity/tf", json={
        "gene_values": {"TP53": 1.0},
        "species": "human",
    })
    assert resp.status_code == 400


def test_pathway_activity():
    resp = client.post("/api/v1/activity/pathway", json={
        "gene_values": {"TP53": 3.0, "MDM2": -2.0, "CDKN1A": 2.5,
                        "BAX": 1.8, "BCL2": -1.5, "GADD45A": 2.1},
        "species": "human",
        "top": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "pathways" in data


def test_benchmark_status():
    resp = client.get("/api/v1/benchmark/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "atlas_summary" in data
    assert "benchmarks" in data
    assert "species_validation" in data
    assert data["atlas_summary"]["genes"] > 0


def test_sirna_pool():
    resp = client.post("/api/v1/dsrna/sirna-pool", json={
        "sequence": "ATGGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTA",
        "k": 21,
        "top": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sirnas"] > 0
    assert "mean_efficacy" in data
    for s in data["top_sirnas"]:
        assert "efficacy_score" in s
        assert 0 <= s["efficacy_score"] <= 1


def test_isoform_coverage():
    resp = client.post("/api/v1/dsrna/isoform-coverage", json={
        "target_gene_id": "Peaxi162Scf00047g01225",
        "species": "petunia",
    })
    assert resp.status_code == 200
    data = resp.json()
    if data.get("available", True):
        assert "isoforms" in data
        assert data["n_isoforms"] >= 1
