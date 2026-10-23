"""Exact restriction mapping and full-digest fragment calculation."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from Bio import __version__ as BIOPYTHON_VERSION
from Bio.Restriction import RestrictionBatch
from Bio.Seq import Seq

from .sequence import canonical_sequence, normalize_topology, sequence_sha256


class UnknownEnzymeError(ValueError):
    pass


def _batch(enzyme_names: Iterable[str]) -> RestrictionBatch:
    names = list(dict.fromkeys(name.strip() for name in enzyme_names if name.strip()))
    if not names:
        raise ValueError("at least one restriction enzyme is required")
    try:
        batch = RestrictionBatch(names)
    except ValueError as exc:
        raise UnknownEnzymeError(str(exc)) from exc
    if len(batch) != len(names):
        recognized = {str(enzyme) for enzyme in batch}
        missing = [name for name in names if name not in recognized]
        raise UnknownEnzymeError(f"unknown restriction enzyme(s): {', '.join(missing)}")
    return batch


def restriction_end(enzyme_name: str) -> dict:
    """Return a normalized cleavage-end descriptor for compatibility checks."""
    enzyme = next(iter(_batch([enzyme_name])))
    end_type = "blunt"
    if enzyme.is_5overhang():
        end_type = "5_prime"
    elif enzyme.is_3overhang():
        end_type = "3_prime"
    return {
        "enzyme": str(enzyme),
        "type": end_type,
        "overhang_sequence": str(enzyme.ovhgseq),
        "overhang_length": abs(enzyme.ovhg),
    }


def ends_compatible(left_enzyme: str, right_enzyme: str) -> dict:
    """Check whether complete cuts produce directly ligatable cohesive/blunt ends."""
    left = restriction_end(left_enzyme)
    right = restriction_end(right_enzyme)
    compatible = (
        left["type"] == right["type"]
        and left["overhang_sequence"] == right["overhang_sequence"]
    )
    return {
        "left": left,
        "right": right,
        "compatible": compatible,
        "reason": "matching cleavage ends" if compatible else "cleavage overhang type or sequence differs",
    }


def _site_record(enzyme, position: int, sequence_length: int, topology: str) -> dict:
    top_cut = position - 1
    if topology == "circular":
        top_cut %= sequence_length
    recognition_start = top_cut - enzyme.fst5
    bottom_cut = recognition_start + enzyme.size + enzyme.fst3
    if topology == "circular":
        recognition_start %= sequence_length
        bottom_cut %= sequence_length
    overhang_type = "blunt"
    if enzyme.is_5overhang():
        overhang_type = "5_prime"
    elif enzyme.is_3overhang():
        overhang_type = "3_prime"
    return {
        "enzyme": str(enzyme),
        "recognition_sequence": enzyme.site,
        "recognition_start": recognition_start,
        "recognition_end": recognition_start + enzyme.size,
        "top_cut": top_cut,
        "bottom_cut": bottom_cut,
        "overhang_type": overhang_type,
        "overhang_length": abs(enzyme.ovhg),
    }


def restriction_map(sequence: str, enzymes: Iterable[str], *, topology: str) -> dict:
    seq = canonical_sequence(sequence)
    topology = normalize_topology(topology)
    batch = _batch(enzymes)
    search = batch.search(Seq(seq), linear=topology == "linear")
    sites = []
    for enzyme in sorted(batch, key=str):
        for position in search.get(enzyme, []):
            sites.append(_site_record(enzyme, position, len(seq), topology))
    sites.sort(key=lambda site: (site["top_cut"], site["enzyme"]))
    return {
        "length": len(seq),
        "topology": topology,
        "sequence_sha256": sequence_sha256(seq),
        "enzymes": sorted(str(enzyme) for enzyme in batch),
        "sites": sites,
        "site_count": len(sites),
        "engine": {"name": "Biopython.Restriction", "version": BIOPYTHON_VERSION},
        "coordinate_system": "zero_based_interbase_cuts",
    }


def _linear_fragments(seq: str, cuts: list[int]) -> list[dict]:
    boundaries = [0, *cuts, len(seq)]
    fragments = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        fragments.append({
            "fragment_index": index,
            "start_cut": start,
            "end_cut": end,
            "length": end - start,
            "sequence": seq[start:end],
            "wraps_origin": False,
        })
    return fragments


def _circular_fragments(seq: str, cuts: list[int]) -> list[dict]:
    if not cuts:
        return []
    if len(cuts) == 1:
        cut = cuts[0]
        return [{
            "fragment_index": 0,
            "start_cut": cut,
            "end_cut": cut,
            "length": len(seq),
            "sequence": seq[cut:] + seq[:cut],
            "wraps_origin": cut != 0,
        }]
    fragments = []
    for index, start in enumerate(cuts):
        end = cuts[(index + 1) % len(cuts)]
        wraps = end <= start
        fragment_sequence = seq[start:end] if not wraps else seq[start:] + seq[:end]
        fragments.append({
            "fragment_index": index,
            "start_cut": start,
            "end_cut": end,
            "length": len(fragment_sequence),
            "sequence": fragment_sequence,
            "wraps_origin": wraps,
        })
    return fragments


def digest_sequence(
    sequence: str,
    enzymes: Iterable[str],
    *,
    topology: str,
    include_fragment_sequences: bool = True,
) -> dict:
    seq = canonical_sequence(sequence)
    topology = normalize_topology(topology)
    mapped = restriction_map(seq, enzymes, topology=topology)
    cuts_to_enzymes: dict[int, list[str]] = defaultdict(list)
    for site in mapped["sites"]:
        cuts_to_enzymes[site["top_cut"]].append(site["enzyme"])
    cuts = sorted(cuts_to_enzymes)
    fragments = _linear_fragments(seq, cuts) if topology == "linear" else _circular_fragments(seq, cuts)
    if not include_fragment_sequences:
        for fragment in fragments:
            fragment.pop("sequence", None)
    warnings = []
    if topology == "circular" and not cuts:
        warnings.append(
            "No enzyme cuts the circular molecule; uncut circular topology is not represented as a linear fragment."
        )
    if len(mapped["sites"]) != len(cuts):
        warnings.append("Multiple enzyme sites share a top-strand cut coordinate and were deduplicated for fragmentation.")
    return {
        **mapped,
        "cut_positions": cuts,
        "cuts": [
            {"position": cut, "enzymes": sorted(cuts_to_enzymes[cut])}
            for cut in cuts
        ],
        "fragments": fragments,
        "fragment_lengths": sorted((fragment["length"] for fragment in fragments), reverse=True),
        "uncut": not cuts,
        "length_conserved": (sum(fragment["length"] for fragment in fragments) == len(seq)) if fragments else None,
        "warnings": warnings,
    }
