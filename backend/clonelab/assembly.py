"""Sequence-level coordinate assembly for verified virtual constructs."""

from __future__ import annotations

from .sequence import canonical_sequence, molecule_sha256, normalize_topology, reverse_complement, sequence_sha256


def assemble_insert(
    vector_sequence: str,
    insert_sequence: str,
    *,
    insertion_start: int,
    insertion_end: int | None = None,
    orientation: str = "forward",
    vector_topology: str = "circular",
    junction_flank: int = 20,
    vector_features: list[dict] | None = None,
    insert_features: list[dict] | None = None,
) -> dict:
    vector = canonical_sequence(vector_sequence)
    insert = canonical_sequence(insert_sequence)
    topology = normalize_topology(vector_topology)
    end = insertion_start if insertion_end is None else insertion_end
    if not (0 <= insertion_start <= end <= len(vector)):
        raise ValueError("insertion interval must satisfy 0 <= start <= end <= vector length")
    if orientation not in {"forward", "reverse"}:
        raise ValueError("orientation must be 'forward' or 'reverse'")
    oriented_insert = insert if orientation == "forward" else reverse_complement(insert)
    construct = vector[:insertion_start] + oriented_insert + vector[end:]
    insert_start = insertion_start
    insert_end = insertion_start + len(oriented_insert)
    left_start = max(0, insert_start - junction_flank)
    right_end = min(len(construct), insert_end + junction_flank)
    features, feature_warnings = remap_assembly_features(
        vector_features or [], insert_features or [],
        insertion_start=insertion_start, insertion_end=end,
        insert_length=len(oriented_insert), orientation=orientation,
    )
    return {
        "sequence": construct,
        "length": len(construct),
        "topology": topology,
        "orientation": orientation,
        "replaced_vector_interval": {"start": insertion_start, "end": end},
        "insert_interval": {"start": insert_start, "end": insert_end},
        "junctions": {
            "left": {
                "position": insert_start,
                "sequence": construct[left_start:min(len(construct), insert_start + junction_flank)],
                "window_start": left_start,
            },
            "right": {
                "position": insert_end,
                "sequence": construct[max(0, insert_end - junction_flank):right_end],
                "window_start": max(0, insert_end - junction_flank),
            },
        },
        "sequence_sha256": sequence_sha256(construct),
        "molecule_sha256": molecule_sha256(construct, topology),
        "components": [
            {"type": "vector", "start": 0, "end": insertion_start, "source_start": 0, "source_end": insertion_start},
            {"type": "insert", "start": insert_start, "end": insert_end, "orientation": orientation},
            {"type": "vector", "start": insert_end, "end": len(construct), "source_start": end, "source_end": len(vector)},
        ],
        "features": features,
        "warnings": feature_warnings,
    }


def remap_assembly_features(vector_features: list[dict], insert_features: list[dict], *,
                            insertion_start: int, insertion_end: int, insert_length: int,
                            orientation: str) -> tuple[list[dict], list[str]]:
    """Remap non-overlapping source features into an assembled construct."""
    shift = insert_length - (insertion_end - insertion_start)
    remapped = []
    warnings = []
    for feature in vector_features:
        item = dict(feature)
        if item["end"] <= insertion_start:
            pass
        elif item["start"] >= insertion_end:
            item["start"] += shift
            item["end"] += shift
        elif insertion_start == insertion_end and item["start"] < insertion_start < item["end"]:
            item["end"] += insert_length
            item["parts"] = [
                {"start": feature["start"], "end": insertion_start, "strand": feature.get("strand")},
                {"start": insertion_start + insert_length, "end": feature["end"] + insert_length, "strand": feature.get("strand")},
            ]
        else:
            warnings.append(f"vector feature {item.get('type', 'feature')} overlapped the replaced interval and was omitted")
            continue
        remapped.append(item)
    for feature in insert_features:
        item = dict(feature)
        if not (0 <= item["start"] < item["end"] <= insert_length):
            raise ValueError("insert feature coordinates are outside the insert sequence")
        if orientation == "forward":
            item["start"] += insertion_start
            item["end"] += insertion_start
        else:
            old_start, old_end = item["start"], item["end"]
            item["start"] = insertion_start + insert_length - old_end
            item["end"] = insertion_start + insert_length - old_start
            if item.get("strand") in (-1, 1):
                item["strand"] *= -1
        remapped.append(item)
    return sorted(remapped, key=lambda item: (item["start"], item["end"])), warnings
