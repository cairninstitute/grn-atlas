"""Tests for Phase 3: M5 trajectory, M7 CRISPR, M8 perturbation, M9 signaling."""
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def _create_dataset_with_contrast():
    resp = client.post("/api/v1/import/omics", json={
        "name": "Trajectory test",
        "species": "human",
        "data_type": "pseudobulk",
        "gene_values": {
            "TP53": [5.2, 3.1], "MDM2": [2.3, 4.5], "CDKN1A": [8.1, 6.2],
            "BAX": [1.5, 2.0], "BCL2": [3.0, 1.0],
        },
        "contrasts": [
            {"group_a": "early", "group_b": "late",
             "deg": {"TP53": 2.5, "MDM2": -1.8, "BAX": 1.2}},
        ],
    })
    data = resp.json()
    return data["dataset_id"], data["contrasts"][0]["contrast_id"]


def test_trajectory_drivers():
    ds_id, ct_id = _create_dataset_with_contrast()
    resp = client.post("/api/v1/trajectory/drivers", json={
        "dataset_id": ds_id,
        "contrasts": [ct_id],
        "species": "human",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "drivers" in data
    assert data["n_contrasts"] == 1


def test_pseudotime_activity():
    ds_id, _ = _create_dataset_with_contrast()
    resp = client.post("/api/v1/trajectory/activity", json={
        "dataset_id": ds_id,
        "gene_values": {"TP53": 3.0, "MDM2": -2.0, "CDKN1A": 2.5,
                        "BAX": 1.8, "BCL2": -1.5, "GADD45A": 2.1},
        "species": "human",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "active_tfs" in data


def test_crispr_offtargets():
    resp = client.post("/api/v1/crispr/offtargets", json={
        "guide_sequence": "ATGGCTAGCTAGCTAGCTAG",
        "species": "arabidopsis",
        "max_mismatches": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "n_offtargets" in data


def test_crispr_offtargets_bad_length():
    resp = client.post("/api/v1/crispr/offtargets", json={
        "guide_sequence": "ATGG",
        "species": "human",
    })
    assert resp.status_code == 400


def test_crispr_compare():
    resp = client.post("/api/v1/crispr/compare", json={
        "gene_id": "TP53",
        "species": "human",
        "modes": ["knockout", "CRISPRi", "CRISPRa"],
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert len(data["strategies"]) == 3
        assert data["strategies"][0]["mode"] == "knockout"


def test_perturbation_import():
    resp = client.post("/api/v1/perturbation/import", json={
        "species": "human",
        "perturbation_type": "CRISPR_KO",
        "observations": [
            {"perturbed_gene": "TP53", "affected_gene": "MDM2", "log2fc": -2.5, "significant": True},
            {"perturbed_gene": "TP53", "affected_gene": "CDKN1A", "log2fc": -3.1, "significant": True},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["n_imported"] == 2


def test_perturbation_compare():
    client.post("/api/v1/perturbation/import", json={
        "species": "human", "perturbation_type": "CRISPR_KO",
        "observations": [
            {"perturbed_gene": "TP53", "affected_gene": "MDM2", "log2fc": -2.5, "significant": True},
        ],
    })
    resp = client.post("/api/v1/perturbation/compare", json={
        "perturbed_gene": "TP53", "species": "human",
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "n_predicted" in data
        assert "concordance_rate" in data


def test_perturbation_calibration():
    resp = client.get("/api/v1/perturbation/calibration")
    assert resp.status_code == 200
    data = resp.json()
    assert "datasets" in data


def test_signaling_to_tf():
    resp = client.post("/api/v1/signaling/to-tf", json={
        "species": "human",
        "receptor_gene": "TP53",
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "direct_tf_targets" in data


def test_ligand_receptor_pairs():
    resp = client.post("/api/v1/signaling/ligand-receptor", json={
        "species": "human",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "pairs" in data
