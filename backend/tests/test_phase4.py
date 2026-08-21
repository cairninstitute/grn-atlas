"""Tests for Phase 4: M11 non-model species transfer, M12 workflow packaging."""
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


def test_transfer_risk():
    resp = client.post("/api/v1/orthology/transfer-risk", json={
        "gene_id": "AT1G56650",
        "target_species": "tomato",
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "risks" in data


def test_family_rescue():
    resp = client.post("/api/v1/family-rescue", json={
        "gene_id": "AT1G56650",
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "rescued_edges" in data


def test_species_onboarding_known():
    resp = client.get("/api/v1/species/onboarding/arabidopsis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["species"] == "arabidopsis"
    assert data["gene_count"] >= 0
    assert "readiness_score" in data
    assert data["readiness_level"] in ("full", "partial", "minimal")


def test_species_onboarding_unknown():
    resp = client.get("/api/v1/species/onboarding/dahlia")
    assert resp.status_code == 200
    data = resp.json()
    assert data["species"] == "dahlia"
    assert data["gene_count"] == 0
    assert data["readiness_level"] == "minimal"


def test_workflow_list():
    resp = client.get("/api/v1/workflows/list")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["workflows"]) >= 3


def test_workflow_deg_to_regulators():
    resp = client.post("/api/v1/workflows/run", json={
        "workflow_type": "deg-to-regulators",
        "species": "human",
        "gene_ids": ["TP53", "MDM2", "CDKN1A", "BAX", "BCL2"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["workflow"] == "deg-to-regulators"
    assert data["status"] == "complete"
    assert "results" in data


def test_workflow_target_perturbation():
    resp = client.post("/api/v1/workflows/run", json={
        "workflow_type": "target-to-perturbation",
        "species": "human",
        "gene_ids": ["TP53"],
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert data["workflow"] == "target-to-perturbation"
        assert "strategies" in data


def test_workflow_import_to_activity():
    ds_resp = client.post("/api/v1/import/omics", json={
        "name": "Workflow test", "species": "human", "data_type": "bulk",
        "gene_values": {"TP53": [5.0], "MDM2": [3.0], "CDKN1A": [8.0]},
    })
    ds_id = ds_resp.json()["dataset_id"]
    resp = client.post("/api/v1/workflows/run", json={
        "workflow_type": "import-to-activity",
        "dataset_id": ds_id,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["workflow"] == "import-to-activity"
    assert data["status"] == "ready"


def test_workflow_unknown():
    resp = client.post("/api/v1/workflows/run", json={
        "workflow_type": "nonexistent",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
    assert "available_workflows" in data
