import json

from clonelab.reports import export_report


def test_json_report_is_hashed_and_reproducible_content_is_parseable():
    report = export_report({"project_id": "clp_1", "name": "Test"}, {"digest": [800, 200]})
    assert report["media_type"] == "application/json"
    assert len(report["sha256"]) == 64
    assert json.loads(report["content"])["analysis"]["digest"] == [800, 200]


def test_markdown_report_states_claim_boundary():
    report = export_report({"name": "Test"}, {}, output_format="markdown")
    assert "# CloneLab Report: Test" in report["content"]
    assert "not experimental observations" in report["content"]
