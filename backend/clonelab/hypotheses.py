"""Generate explicit molecular alternatives from one vector/insert design."""

from __future__ import annotations

from .assembly import assemble_insert
from .sequence import canonical_sequence, molecule_sha256, normalize_topology, sequence_sha256


def construct_hypotheses(
    vector_sequence: str,
    insert_sequence: str,
    *,
    insertion_start: int,
    insertion_end: int | None = None,
    vector_topology: str = "circular",
    include_tandem: bool = False,
) -> list[dict]:
    vector = canonical_sequence(vector_sequence)
    insert = canonical_sequence(insert_sequence)
    topology = normalize_topology(vector_topology)
    end = insertion_start if insertion_end is None else insertion_end
    forward = assemble_insert(
        vector, insert, insertion_start=insertion_start, insertion_end=end,
        orientation="forward", vector_topology=topology,
    )
    reverse = assemble_insert(
        vector, insert, insertion_start=insertion_start, insertion_end=end,
        orientation="reverse", vector_topology=topology,
    )
    empty_sequence = vector[:insertion_start] + vector[end:]
    results = [
        {"hypothesis_id": "intended", "label": "Correct insert orientation", **forward},
        {"hypothesis_id": "reverse", "label": "Reverse insert orientation", **reverse},
        {
            "hypothesis_id": "empty",
            "label": "Empty vector",
            "sequence": empty_sequence,
            "length": len(empty_sequence),
            "topology": topology,
            "sequence_sha256": sequence_sha256(empty_sequence),
            "molecule_sha256": molecule_sha256(empty_sequence, topology),
        },
    ]
    if include_tandem:
        tandem = assemble_insert(
            vector, insert + insert, insertion_start=insertion_start, insertion_end=end,
            orientation="forward", vector_topology=topology,
        )
        results.append({"hypothesis_id": "tandem", "label": "Tandem insert", **tandem})
    return results
