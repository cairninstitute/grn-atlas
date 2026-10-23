import pytest

from clonelab.restriction import UnknownEnzymeError, digest_sequence, ends_compatible, restriction_map

from backend.tests.clonelab.helpers import molecule


def test_linear_digest_uses_interbase_coordinates_and_conserves_length():
    sequence = molecule(100, {10: "GAATTC", 60: "GGATCC"})
    result = digest_sequence(sequence, ["EcoRI", "BamHI"], topology="linear")
    assert result["cut_positions"] == [11, 61]
    assert result["fragment_lengths"] == [50, 39, 11]
    assert result["length_conserved"] is True
    assert sum(result["fragment_lengths"]) == len(sequence)


def test_circular_digest_returns_origin_spanning_fragment():
    sequence = molecule(100, {10: "GAATTC", 60: "GGATCC"})
    result = digest_sequence(sequence, ["EcoRI", "BamHI"], topology="circular")
    assert result["fragment_lengths"] == [50, 50]
    assert result["length_conserved"] is True
    assert any(fragment["wraps_origin"] for fragment in result["fragments"])


def test_single_cut_linearizes_circular_molecule():
    sequence = molecule(100, {10: "GAATTC"})
    result = digest_sequence(sequence, ["EcoRI"], topology="circular")
    assert result["fragment_lengths"] == [100]
    assert result["fragments"][0]["sequence"] == sequence[11:] + sequence[:11]


def test_uncut_circular_molecule_is_not_reported_as_linear_fragment():
    result = digest_sequence("C" * 100, ["EcoRI"], topology="circular")
    assert result["uncut"] is True
    assert result["fragments"] == []
    assert result["length_conserved"] is None
    assert "uncut circular topology" in result["warnings"][0]


def test_map_reports_overhang_and_recognition_coordinates():
    sequence = molecule(100, {10: "GAATTC"})
    result = restriction_map(sequence, ["EcoRI"], topology="linear")
    assert result["sites"][0] == {
        "enzyme": "EcoRI",
        "recognition_sequence": "GAATTC",
        "recognition_start": 10,
        "recognition_end": 16,
        "top_cut": 11,
        "bottom_cut": 15,
        "overhang_type": "5_prime",
        "overhang_length": 4,
    }


def test_unknown_enzyme_fails_explicitly():
    with pytest.raises(UnknownEnzymeError):
        restriction_map("ACGT", ["DefinitelyNotAnEnzyme"], topology="linear")


@pytest.mark.parametrize("topology", ["linear", "circular"])
def test_digest_length_conservation_across_deterministic_site_positions(topology):
    for offset in range(0, 80, 7):
        sequence = molecule(100, {offset: "GAATTC"})
        result = digest_sequence(sequence, ["EcoRI"], topology=topology)
        assert sum(result["fragment_lengths"]) == len(sequence)
        assert result["length_conserved"] is True


def test_restriction_end_compatibility_is_sequence_specific():
    assert ends_compatible("EcoRI", "EcoRI")["compatible"] is True
    assert ends_compatible("EcoRI", "XhoI")["compatible"] is False
    assert ends_compatible("SmaI", "SmaI")["compatible"] is True
