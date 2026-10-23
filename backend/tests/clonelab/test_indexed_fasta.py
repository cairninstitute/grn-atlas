from clonelab.indexed_fasta import IndexedFasta, build_fasta_index


def test_indexed_fasta_fetches_across_lines(tmp_path):
    fasta = tmp_path / "genome.fa"
    fasta.write_text(">Chr1\nAACCG\nGTTAC\nGT\n>scaffold\nTTTT\n")
    index = build_fasta_index(fasta)
    genome = IndexedFasta(fasta, index)
    assert genome.length("Chr1") == 12
    assert genome.fetch("Chr1", 3, 10) == "CGGTTAC"
