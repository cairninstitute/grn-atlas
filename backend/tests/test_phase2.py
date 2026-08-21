"""Tests for Phase 2: M1 omics import, M3 cell-type workflows, M4 chromatin layer."""
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def test_import_omics():
    resp = client.post("/api/v1/import/omics", json={
        "name": "Test bulk",
        "species": "human",
        "data_type": "bulk",
        "gene_values": {
            "TP53": [5.2, 3.1, 7.8],
            "MDM2": [2.3, 4.5, 1.2],
            "CDKN1A": [8.1, 6.2, 9.3],
            "BAX": [1.5, 2.0, 3.0],
        },
        "sample_names": ["S1", "S2", "S3"],
        "contrasts": [{"group_a": "treated", "group_b": "control",
                       "deg": {"TP53": 2.5, "MDM2": -1.8, "CDKN1A": 3.1, "BAX": 0.2}}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["n_features"] == 4
    assert data["n_samples"] == 3
    assert len(data["contrasts"]) == 1
    return data["dataset_id"]


def test_import_and_retrieve():
    ds_id = test_import_omics()
    resp = client.get(f"/api/v1/import/{ds_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset_id"] == ds_id
    assert data["species"] == "human"
    assert len(data["contrasts"]) == 1


def test_import_validate():
    ds_id = test_import_omics()
    resp = client.post(f"/api/v1/import/{ds_id}/validate")
    assert resp.status_code == 200
    data = resp.json()
    assert "match_pct" in data
    assert data["imported_features"] == 4


def test_list_imported():
    test_import_omics()
    resp = client.get("/api/v1/import/list/all")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["datasets"]) >= 1


def test_celltype_regulation():
    ds_id = test_import_omics()
    resp = client.post("/api/v1/celltype/regulation", json={
        "dataset_id": ds_id,
        "cluster_id": "default",
        "species": "human",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "regulators" in data or "n_expressed_genes" in data


def test_celltype_regulation_tp53_regression():
    resp = client.post("/api/v1/import/omics", json={
        "name": "TP53 context",
        "species": "human",
        "data_type": "bulk",
        "gene_values": {
            "TP53": [5.0, 1.0],
            "MDM2": [1.0, 5.0],
            "CDKN1A": [4.0, 1.0],
            "BAX": [3.0, 1.0],
            "BCL2": [1.0, 4.0],
        },
        "sample_names": ["A", "B"],
    })
    ds_id = resp.json()["dataset_id"]
    resp = client.post("/api/v1/celltype/regulation", json={
        "dataset_id": ds_id,
        "cluster_id": "default",
        "species": "human",
        "top": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    top_symbols = [r["symbol"] for r in data["regulators"][:5]]
    assert "TP53" in top_symbols


def test_celltype_upstream():
    ds_id = test_import_omics()
    resp = client.post("/api/v1/celltype/upstream", json={
        "dataset_id": ds_id,
        "cluster_id": "default",
        "gene_ids": ["TP53", "MDM2", "CDKN1A"],
        "species": "human",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "regulators" in data


def test_celltype_compare():
    ds_id = test_import_omics()
    resp = client.post("/api/v1/celltype/compare", json={
        "dataset_id": ds_id,
        "cluster_a": "treated",
        "cluster_b": "control",
        "species": "human",
    })
    assert resp.status_code == 200


def test_import_peaks():
    resp = client.post("/api/v1/chromatin/import-peaks", json={
        "species": "arabidopsis",
        "peaks": [
            {"chrom": "Chr1", "start": 1000, "end": 2000, "score": 50.5, "peak_type": "promoter"},
            {"chrom": "Chr1", "start": 5000, "end": 6000, "score": 30.2, "peak_type": "enhancer"},
        ],
        "links": [
            {"peak_id": "Chr1:1000-2000", "gene_id": "AT1G01010", "score": 0.8, "link_type": "proximity"},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["n_peaks"] == 2
    assert data["n_links"] == 1


def test_chromatin_peaks():
    test_import_peaks()
    resp = client.get("/api/v1/chromatin/peaks/arabidopsis")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["peaks"]) >= 1


def test_chromatin_gene_support():
    test_import_peaks()
    resp = client.get("/api/v1/chromatin/gene/AT1G01010")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gene_id"] == "AT1G01010"
    assert len(data["linked_peaks"]) >= 1


def test_cis_support_query():
    resp = client.post("/api/v1/chromatin/cis-support?gene_id=AT1G01010")
    assert resp.status_code == 200
    data = resp.json()
    assert "edges" in data
