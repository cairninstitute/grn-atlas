from clonelab.formats import export_fasta, export_genbank, parse_sequences


def test_parse_multi_record_fasta_and_round_trip():
    records = parse_sequences(">one first\nacgt\n>two second\nTTAA\n", default_topology="linear")
    assert [record["sequence"] for record in records] == ["ACGT", "TTAA"]
    assert parse_sequences(export_fasta(records[0]))[0]["sequence"] == "ACGT"


def test_genbank_round_trip_preserves_topology_sequence_and_features():
    record = {
        "name": "pTest",
        "accession": "TEST0001",
        "description": "CloneLab fixture",
        "sequence": "AACCGGTTAACC",
        "topology": "circular",
        "annotations": {"date": "23-OCT-2026"},
        "features": [{
            "type": "promoter",
            "start": 2,
            "end": 9,
            "strand": -1,
            "parts": [{"start": 2, "end": 9, "strand": -1}],
            "qualifiers": {"label": ["test promoter"]},
        }],
    }
    parsed = parse_sequences(export_genbank(record), file_format="genbank")[0]
    assert parsed["sequence"] == record["sequence"]
    assert parsed["topology"] == "circular"
    assert parsed["features"][0]["start"] == 2
    assert parsed["features"][0]["end"] == 9
    assert parsed["features"][0]["strand"] == -1
