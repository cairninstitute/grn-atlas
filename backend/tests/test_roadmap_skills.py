"""Tests for the 10-skill roadmap: Phase 1-3 endpoints."""
from starlette.testclient import TestClient
from main import app

client = TestClient(app)


# Phase 1

def test_cis_support_audit():
    resp = client.post("/api/v1/cis-support/audit", json={
        "source_id": "AT1G56650", "target_id": "AT5G42910",
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "confidence_tier" in data
        assert "layers" in data
        assert "missing_layers" in data


def test_cis_support_audit_nonexistent():
    resp = client.post("/api/v1/cis-support/audit", json={
        "source_id": "FAKE_TF", "target_id": "FAKE_TARGET",
    })
    assert resp.status_code == 404


def test_enhancer_network():
    resp = client.post("/api/v1/enhancer/network", json={
        "gene_id": "AT1G56650",
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "linked_peaks" in data
        assert "enhancer_regulators" in data
        assert "co_linked_targets" in data


def test_peak_gene_linkage_by_peak():
    resp = client.post("/api/v1/peak-gene/linkage", json={
        "peak_id": "chr1:1000-2000",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "linked_genes" in data


def test_peak_gene_linkage_by_region():
    resp = client.post("/api/v1/peak-gene/linkage", json={
        "region": "chr1:1000-2000", "species": "arabidopsis",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "peaks" in data


def test_peak_gene_linkage_no_input():
    resp = client.post("/api/v1/peak-gene/linkage", json={})
    assert resp.status_code == 400


def test_crispr_vs_dsrna():
    resp = client.post("/api/v1/compare/crispr-vs-dsrna", json={
        "gene_ids": ["AT1G56650"], "species": "arabidopsis",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "comparisons" in data
    assert len(data["comparisons"]) >= 1
    c = data["comparisons"][0]
    assert "crispr" in c
    assert "dsrna" in c
    assert "recommendation" in c


def test_edit_consequence_promoter():
    resp = client.post("/api/v1/edit/consequence", json={
        "gene_id": "AT1G56650", "edit_type": "promoter_disruption",
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "consequences" in data
        assert "edit_type" in data
        assert data["edit_type"] == "promoter_disruption"


def test_edit_consequence_coding():
    resp = client.post("/api/v1/edit/consequence", json={
        "gene_id": "AT1G56650", "edit_type": "coding_disruption",
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "downstream_cascade_size" in data


# Phase 2

def test_celltype_regulon():
    resp = client.post("/api/v1/celltype/regulon", json={
        "gene_id": "AT1G56650",
    })
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "global_regulon_size" in data
        assert "state_regulon_size" in data
        assert "state_targets" in data


def test_transition_drivers():
    resp = client.post("/api/v1/transition/drivers", json={
        "species": "arabidopsis",
        "gene_ids": ["AT1G56650", "AT5G42910", "AT3G23230", "AT1G01010"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "drivers" in data or "status" in data


def test_transition_drivers_no_genes():
    resp = client.post("/api/v1/transition/drivers", json={
        "species": "arabidopsis",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ready"


def test_multiome_audit():
    resp = client.post("/api/v1/multiome/audit", json={
        "source_id": "AT1G56650", "target_id": "AT5G42910",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "layers" in data
    assert "n_supporting_layers" in data
    assert "evidence_weight" in data
    assert set(data["layers"].keys()) == {"network", "motif", "chromatin", "expression", "perturbation"}


# Phase 3

def test_literature_grounding():
    resp = client.post("/api/v1/literature/grounding", json={
        "terms": ["MYB75", "AN2", "TP53", "NONEXISTENT_XYZZY"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "mappings" in data
    assert "resolution_rate" in data
    assert data["n_terms"] == 4


def test_literature_grounding_empty():
    resp = client.post("/api/v1/literature/grounding", json={
        "terms": ["TOTALLY_FAKE_GENE"],
    })
    assert resp.status_code == 200
    data = resp.json()
    found = [m for m in data["mappings"] if m["match_type"] != "unresolved"]


def test_intervention_ranker():
    resp = client.post("/api/v1/intervention/rank", json={
        "gene_ids": ["AT1G56650"], "species": "arabidopsis",
        "intent": "knockdown", "budget": "low",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "candidates" in data
    if data["candidates"]:
        c = data["candidates"][0]
        assert "strategies" in c
        assert "recommended" in c
        assert len(c["strategies"]) >= 2


def test_intervention_ranker_knockout():
    resp = client.post("/api/v1/intervention/rank", json={
        "gene_ids": ["AT1G56650"], "species": "arabidopsis",
        "intent": "knockout", "budget": "moderate",
    })
    assert resp.status_code == 200
    data = resp.json()
    if data["candidates"]:
        assert data["candidates"][0]["recommended"] == "CRISPR_KO"
