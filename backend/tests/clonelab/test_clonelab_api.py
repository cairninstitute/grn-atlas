from fastapi import FastAPI
from fastapi.testclient import TestClient

from clonelab.router import router

from backend.tests.clonelab.helpers import diagnostic_hypotheses, molecule


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_digest_api():
    response = client.post("/api/v1/clonelab/digests", json={
        "molecule": {
            "name": "test plasmid",
            "sequence": molecule(100, {10: "GAATTC", 60: "GGATCC"}),
            "topology": "circular",
        },
        "enzymes": ["EcoRI", "BamHI"],
        "include_fragment_sequences": False,
    })
    assert response.status_code == 200
    assert response.json()["fragment_lengths"] == [50, 50]
    assert "sequence" not in response.json()["fragments"][0]


def test_optimizer_api():
    response = client.post("/api/v1/clonelab/assays/optimize", json={
        "hypotheses": [
            {"name": h["label"], **h}
            for h in diagnostic_hypotheses()
        ],
        "candidate_enzymes": ["EcoRI", "XhoI", "HindIII"],
        "min_fragment_bp": 0,
        "min_separation_bp": 0,
        "relative_resolution": 0,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["best_digest"]["enzymes"] == ["EcoRI", "XhoI"]
    assert result["best_digest"]["fully_discriminatory"] is True


def test_api_rejects_unknown_enzyme():
    response = client.post("/api/v1/clonelab/restriction/map", json={
        "molecule": {"name": "x", "sequence": "ACGT", "topology": "linear"},
        "enzymes": ["NotARealEnzyme"],
    })
    assert response.status_code == 422


def test_project_sequence_import_and_retrieval_api(tmp_path, monkeypatch):
    monkeypatch.setenv("CLONELAB_DB", str(tmp_path / "clonelab.sqlite3"))
    project_response = client.post("/api/v1/clonelab/projects", json={
        "name": "Arabidopsis clock",
        "darwin_context": {"species": "arabidopsis", "gene": "CCA1"},
    })
    assert project_response.status_code == 200
    project_id = project_response.json()["project_id"]

    import_response = client.post("/api/v1/clonelab/sequences/import", json={
        "content": ">clock_promoter\nAACCGGTT\n",
        "file_format": "fasta",
        "default_topology": "linear",
        "source": "test fixture",
        "project_id": project_id,
    })
    assert import_response.status_code == 200
    sequence_id = import_response.json()["sequences"][0]["sequence_id"]
    retrieved = client.get(f"/api/v1/clonelab/sequences/{sequence_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["sequence"] == "AACCGGTT"
    assert client.get(f"/api/v1/clonelab/projects/{project_id}").json()["sequences"][0]["length"] == 8


def test_construct_hypotheses_api():
    response = client.post("/api/v1/clonelab/constructs/hypotheses", json={
        "vector": {"name": "vector", "sequence": "AAAATTTT", "topology": "circular"},
        "insert": {"name": "insert", "sequence": "AAGC", "topology": "linear"},
        "insertion_start": 4,
        "include_tandem": True,
    })
    assert response.status_code == 200
    assert [item["hypothesis_id"] for item in response.json()["hypotheses"]] == [
        "intended", "reverse", "empty", "tandem"
    ]


def test_sequence_import_limit_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("CLONELAB_DB", str(tmp_path / "clonelab.sqlite3"))
    monkeypatch.setenv("CLONELAB_MAX_INPUT_BASES", "4")
    response = client.post("/api/v1/clonelab/sequences/import", json={
        "content": ">too_long\nAACCGGTT\n",
        "file_format": "fasta",
    })
    assert response.status_code == 413


def test_full_diagnostic_workflow_api():
    response = client.post("/api/v1/clonelab/workflows/diagnostic-digest", json={
        "vector": {"name": "vector", "sequence": molecule(1000, {100: "GAATTC", 700: "CTCGAG"}), "topology": "circular"},
        "insert": {"name": "insert", "sequence": "AAGCTT" + "C" * 94, "topology": "linear"},
        "insertion_start": 400,
        "candidate_enzymes": ["EcoRI", "XhoI", "HindIII"],
        "min_fragment_bp": 1,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["optimization"]["best_digest"]
    assert body["gel"]["simulation"] is True
    assert body["provenance"]["biopython"] == "1.88"
