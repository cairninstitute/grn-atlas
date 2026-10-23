import json
import sqlite3

from clonelab.indexed_fasta import build_fasta_index
from clonelab.promoter import retrieve_promoter
from clonelab.reference import ReferenceRegistry


def _fixture(tmp_path):
    fasta = tmp_path / "genome.fa"
    fasta.write_text(">Chr1\n" + "ACGT" * 100 + "\n")
    index = build_fasta_index(fasta)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"references": [{
        "species": "plant", "assembly": "v1", "molecule_type": "genome",
        "path": fasta.name, "index_path": index.name, "source": "fixture",
    }]}))
    database = tmp_path / "atlas.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE gene_id_crosswalk(species TEXT, atlas_gene_id TEXT, ext_gene_id TEXT, ext_assembly TEXT);
        CREATE TABLE gene_windows(ext_gene_id TEXT, assembly TEXT, window_type TEXT, chromosome TEXT, start INTEGER, end INTEGER, strand INTEGER);
        INSERT INTO gene_id_crosswalk VALUES ('plant','plus','g1','v1'), ('plant','minus','g2','v1');
        INSERT INTO gene_windows VALUES ('g1','v1','gene_body','Chr1',100,140,1), ('g2','v1','gene_body','Chr1',200,240,-1);
    """)
    connection.commit(); connection.close()
    return ReferenceRegistry(manifest), database


def test_promoter_retrieval_is_tss_and_strand_aware(tmp_path):
    registry, database = _fixture(tmp_path)
    plus = retrieve_promoter(registry, database, species="plant", gene_id="plus", upstream=20, downstream=5)
    minus = retrieve_promoter(registry, database, species="plant", gene_id="minus", upstream=20, downstream=5)
    assert plus["interval"] == {"start": 80, "end": 105, "strand": 1}
    assert minus["interval"] == {"start": 235, "end": 260, "strand": -1}
    assert len(plus["sequence"]) == len(minus["sequence"]) == 25
    assert minus["orientation"] == "transcriptional_5_to_3"
