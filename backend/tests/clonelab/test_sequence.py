import pytest

from clonelab.sequence import canonical_sequence, molecule_sha256, reverse_complement, sequence_sha256


def test_sequence_normalization_and_hash_are_stable():
    assert canonical_sequence("acgu\n n") == "ACGTN"
    assert sequence_sha256("ACGT") == sequence_sha256(" acgt\n")


def test_reverse_complement_supports_iupac():
    assert reverse_complement("ACGTRYN") == "NRYACGT"


def test_sequence_rejects_non_dna_symbols():
    with pytest.raises(ValueError, match="invalid DNA symbols"):
        canonical_sequence("ACGTZ")


def test_molecule_hash_ignores_circular_origin_and_display_strand():
    sequence = "AACCGGTTACGT"
    rotated = sequence[5:] + sequence[:5]
    assert molecule_sha256(sequence, "circular") == molecule_sha256(rotated, "circular")
    assert molecule_sha256(sequence, "circular") == molecule_sha256(
        reverse_complement(sequence), "circular"
    )


def test_linear_molecule_hash_ignores_display_strand_but_not_rotation():
    sequence = "AACCGGTTACGA"
    assert molecule_sha256(sequence, "linear") == molecule_sha256(reverse_complement(sequence), "linear")
    assert molecule_sha256(sequence, "linear") != molecule_sha256(sequence[1:] + sequence[:1], "linear")
