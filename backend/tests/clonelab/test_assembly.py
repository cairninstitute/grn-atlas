from clonelab.assembly import assemble_insert
from clonelab.hypotheses import construct_hypotheses
from clonelab.sequence import reverse_complement


def test_assembly_generates_complete_sequence_and_exact_junctions():
    result = assemble_insert(
        "AAAACCCC",
        "GGTT",
        insertion_start=4,
        orientation="forward",
        vector_topology="circular",
        junction_flank=2,
    )
    assert result["sequence"] == "AAAAGGTTCCCC"
    assert result["junctions"]["left"]["sequence"] == "AAGG"
    assert result["junctions"]["right"]["sequence"] == "TTCC"
    assert result["insert_interval"] == {"start": 4, "end": 8}


def test_reverse_orientation_uses_reverse_complement():
    result = assemble_insert("AAAACCCC", "AAGC", insertion_start=4, orientation="reverse")
    assert result["sequence"] == "AAAA" + reverse_complement("AAGC") + "CCCC"


def test_construct_hypotheses_are_explicit_molecular_states():
    results = construct_hypotheses(
        "AAAATTTT",
        "CCGG",
        insertion_start=4,
        include_tandem=True,
    )
    by_id = {result["hypothesis_id"]: result for result in results}
    assert set(by_id) == {"intended", "reverse", "empty", "tandem"}
    assert by_id["empty"]["sequence"] == "AAAATTTT"
    assert by_id["tandem"]["length"] == 16


def test_assembly_remaps_insert_features_in_reverse_orientation():
    result = assemble_insert(
        "AAAACCCC", "AAGCTT", insertion_start=4, orientation="reverse",
        vector_features=[{"type": "origin", "start": 0, "end": 3, "strand": 1}],
        insert_features=[{"type": "promoter", "start": 1, "end": 4, "strand": 1}],
    )
    assert result["features"] == [
        {"type": "origin", "start": 0, "end": 3, "strand": 1},
        {"type": "promoter", "start": 6, "end": 9, "strand": -1},
    ]
