import json
from pathlib import Path

from starlette.testclient import TestClient

import main


client = TestClient(main.app)


def test_benchmark_status_includes_artifact_health():
    resp = client.get("/api/v1/benchmark/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "artifact_health" in data
    assert "status" in data["artifact_health"]
    assert "warnings" in data["artifact_health"]


def test_benchmark_status_degrades_when_schema_report_missing(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    runs_dir = data_dir / "validation_runs"
    runs_dir.mkdir(parents=True)

    (data_dir / "beeline_benchmark_report.json").write_text("[]")
    (data_dir / "network_validation_report.md").write_text("# report\n")
    (runs_dir / "latest_summary.json").write_text(json.dumps({"suite_status": "pass"}))
    (runs_dir / "artifact_manifest.json").write_text(json.dumps({"artifacts": []}))

    monkeypatch.setattr(main, "FilePath", lambda *parts: Path(*parts))
    monkeypatch.setattr(main, "__file__", str(tmp_path / "main.py"))

    resp = client.get("/api/v1/benchmark/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifact_health"]["status"] == "degraded"
    assert any("schema_report.json" in warning for warning in data["artifact_health"]["warnings"])
