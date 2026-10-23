"""DNA sequence primitives with explicit normalization and topology semantics."""

from __future__ import annotations

import hashlib
import re

DNA_IUPAC = frozenset("ACGTRYSWKMBDHVN")
_COMPLEMENT = str.maketrans(
    "ACGTRYSWKMBDHVN",
    "TGCAYRSWMKVHDBN",
)


def canonical_sequence(sequence: str, *, allow_ambiguous: bool = True) -> str:
    """Return uppercase DNA with whitespace removed, or raise on invalid symbols."""
    if not isinstance(sequence, str):
        raise TypeError("sequence must be a string")
    normalized = re.sub(r"\s+", "", sequence).upper().replace("U", "T")
    if not normalized:
        raise ValueError("sequence is empty")
    allowed = DNA_IUPAC if allow_ambiguous else frozenset("ACGT")
    invalid = sorted(set(normalized) - allowed)
    if invalid:
        raise ValueError(f"sequence contains invalid DNA symbols: {', '.join(invalid)}")
    return normalized


def reverse_complement(sequence: str) -> str:
    seq = canonical_sequence(sequence)
    return seq.translate(_COMPLEMENT)[::-1]


def sequence_sha256(sequence: str) -> str:
    return hashlib.sha256(canonical_sequence(sequence).encode("ascii")).hexdigest()


def _minimal_rotation(sequence: str) -> str:
    """Lexicographically minimal rotation using Booth's linear-time algorithm."""
    if not sequence:
        return sequence
    doubled = sequence + sequence
    length = len(sequence)
    left, right, offset = 0, 1, 0
    while left < length and right < length and offset < length:
        a, b = doubled[left + offset], doubled[right + offset]
        if a == b:
            offset += 1
            continue
        if a > b:
            left = left + offset + 1
            if left <= right:
                left = right + 1
        else:
            right = right + offset + 1
            if right <= left:
                right = left + 1
        offset = 0
    start = min(left, right)
    return doubled[start:start + length]


def canonical_molecule_sequence(sequence: str, topology: str) -> str:
    """Canonicalize double-stranded molecular identity across strand and circular origin."""
    seq = canonical_sequence(sequence)
    topology = normalize_topology(topology)
    reverse = reverse_complement(seq)
    if topology == "linear":
        return min(seq, reverse)
    return min(_minimal_rotation(seq), _minimal_rotation(reverse))


def molecule_sha256(sequence: str, topology: str) -> str:
    canonical = canonical_molecule_sequence(sequence, topology)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def normalize_topology(topology: str) -> str:
    value = (topology or "").strip().lower()
    if value not in {"linear", "circular"}:
        raise ValueError("topology must be 'linear' or 'circular'")
    return value
