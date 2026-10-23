import pytest

from clonelab.storage import CloneLabStore


def test_project_and_sequence_survive_store_reopen(tmp_path):
    path = tmp_path / "clonelab.sqlite3"
    store = CloneLabStore(path)
    project = store.create_project("Clock construct", darwin_context={"gene": "CCA1"})
    sequence = store.save_sequence({
        "name": "promoter",
        "sequence": "AACCGGTT",
        "topology": "linear",
        "format": "fasta",
        "features": [{"type": "promoter", "start": 1, "end": 7, "strand": 1}],
    }, project["project_id"])

    reopened = CloneLabStore(path)
    retrieved = reopened.get_sequence(sequence["sequence_id"])
    assert retrieved["sequence"] == "AACCGGTT"
    assert retrieved["features"][0]["type"] == "promoter"
    assert reopened.get_project(project["project_id"])["sequences"][0]["sequence_id"] == sequence["sequence_id"]


def test_same_sequence_can_be_imported_into_two_projects(tmp_path):
    store = CloneLabStore(tmp_path / "clonelab.sqlite3")
    first = store.create_project("First")
    second = store.create_project("Second")
    record = {"name": "same", "sequence": "ACGT", "topology": "linear"}
    a = store.save_sequence(record, first["project_id"])
    b = store.save_sequence(record, second["project_id"])
    assert a["sequence_id"] != b["sequence_id"]
    assert a["molecule_sha256"] == b["molecule_sha256"]


def test_invalid_feature_is_rejected(tmp_path):
    store = CloneLabStore(tmp_path / "clonelab.sqlite3")
    with pytest.raises(ValueError, match="outside sequence length"):
        store.save_sequence({
            "name": "bad",
            "sequence": "ACGT",
            "features": [{"type": "gene", "start": 1, "end": 8}],
        })


def test_construct_assay_and_report_are_persisted_as_project_artifacts(tmp_path):
    store = CloneLabStore(tmp_path / "clonelab.sqlite3")
    project = store.create_project("Persistent workflow")
    construct = store.save_construct(project["project_id"], {
        "label": "intended", "sequence": "AACCGGTT", "topology": "circular",
    })
    assay = store.save_assay(project["project_id"], {
        "assay_type": "diagnostic_digest", "enzymes": ["EcoRI"],
    })
    report = store.save_report(project["project_id"], {
        "format": "json", "sha256": "a" * 64, "content": "{}",
    })
    refreshed = store.get_project(project["project_id"])
    assert refreshed["construct_ids"] == [construct["construct_id"]]
    assert refreshed["assay_ids"] == [assay["assay_id"]]
    assert refreshed["report_ids"] == [report["report_id"]]
