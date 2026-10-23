from clonelab.workflow import optimize_construct_design

from backend.tests.clonelab.helpers import molecule


def test_diagnostic_workflow_is_directly_callable_and_traceable():
    vector = molecule(1000, {100: "GAATTC", 700: "CTCGAG"})
    result = optimize_construct_design(
        vector,
        "AAGCTT" + "C" * 94,
        insertion_start=400,
        candidate_enzymes=["EcoRI", "XhoI", "HindIII"],
        min_fragment_bp=1,
    )
    assert result["optimization"]["best_digest"] is not None
    assert len(result["hypotheses"]) == 4
    assert result["gel"]["simulation"] is True
    assert result["provenance"]["biopython"]
    assert "biological function" in result["verification_scope"]["not_established"]
