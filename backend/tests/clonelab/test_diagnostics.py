from clonelab.diagnostics import optimize_digests

from backend.tests.clonelab.helpers import diagnostic_hypotheses


def test_double_digest_is_ranked_first_when_it_uniquely_resolves_all_states():
    result = optimize_digests(
        diagnostic_hypotheses(),
        ["EcoRI", "XhoI", "HindIII"],
        min_fragment_bp=0,
        min_separation_bp=0,
        relative_resolution=0,
    )
    best = result["best_digest"]
    assert best["enzymes"] == ["EcoRI", "XhoI"]
    assert best["fully_discriminatory"] is True
    assert best["pairwise_distinguishable"] == 3
    assert best["predictions"]["intended"]["visible_signature"] == [800, 200]
    assert best["predictions"]["reverse"]["visible_signature"] == [600, 400]
    assert best["predictions"]["empty"]["visible_signature"] == [1000]
    assert result["no_unique_digest"] is False


def test_optimizer_reports_non_identifiability_instead_of_forcing_winner():
    hypotheses = diagnostic_hypotheses()[:2]
    hypotheses[1]["sequence"] = hypotheses[0]["sequence"]
    result = optimize_digests(hypotheses, ["EcoRI", "XhoI"])
    assert result["no_unique_digest"] is True
    assert result["best_digest"]["fully_discriminatory"] is False
    assert result["best_digest"]["pairwise_distinguishable"] == 0


def test_resolution_model_merges_nearby_bands():
    hypotheses = [
        {
            "hypothesis_id": "a",
            "sequence": molecule,
            "topology": "linear",
        }
        for molecule in ("C" * 1000, "C" * 1001)
    ]
    hypotheses[1]["hypothesis_id"] = "b"
    result = optimize_digests(
        hypotheses,
        ["EcoRI"],
        min_fragment_bp=0,
        max_fragment_bp=2000,
    )
    assert result["no_unique_digest"] is True


def test_claim_boundary_does_not_overstate_sequence_identity():
    result = optimize_digests(diagnostic_hypotheses(), ["EcoRI", "XhoI"])
    assert "does not establish base-perfect sequence identity" in result["claim_boundary"]["sequence_identity"]
