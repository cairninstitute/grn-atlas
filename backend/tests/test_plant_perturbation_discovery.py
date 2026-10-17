import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import discover_plant_perturbations  # noqa: E402


def test_discovery_marks_reviewed_accessions_without_approving_other_candidates():
    payload = {"experiments": [
        {
            "experimentAccession": "APPROVED",
            "experimentDescription": "Rice TF knockout",
            "experimentType": "Differential",
            "species": "Oryza sativa",
        },
        {
            "experimentAccession": "NEW",
            "experimentDescription": "Rice TF overexpression",
            "experimentType": "Differential",
            "species": "Oryza sativa",
        },
    ]}

    report = discover_plant_perturbations.discover(payload, {"APPROVED"})
    statuses = {item["accession"]: item["status"] for item in report["species"]["rice"]}

    assert statuses == {
        "APPROVED": "approved_manifest_present",
        "NEW": "candidate_requires_contrast_and_identifier_review",
    }
