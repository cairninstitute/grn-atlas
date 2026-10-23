import hashlib
import json

import pytest

from clonelab.reference import ReferenceNotReadyError, ReferenceRegistry
from clonelab.sequence import reverse_complement


def registry(tmp_path):
    fasta = tmp_path / "reference.fa"
    fasta.write_text(">chr1\nAACCGGTTACGT\n")
    digest = hashlib.sha256(fasta.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"references": [{
        "species": "arabidopsis", "assembly": "TAIR10", "path": "reference.fa",
        "sha256": digest, "source": "test fixture", "accession": "TEST1",
    }]}))
    return ReferenceRegistry(manifest)


def test_reference_interval_is_strand_correct_and_traceable(tmp_path):
    ref = registry(tmp_path)
    forward = ref.retrieve(species="arabidopsis", assembly="TAIR10", record_id="chr1", start=2, end=9)
    reverse = ref.retrieve(species="arabidopsis", assembly="TAIR10", record_id="chr1", start=2, end=9, strand=-1)
    assert reverse["sequence"] == reverse_complement(forward["sequence"])
    assert forward["coordinate_system"] == "zero_based_half_open"
    assert ref.verify()[0]["valid"] is True


def test_missing_assembly_is_a_readiness_error(tmp_path):
    ref = registry(tmp_path)
    with pytest.raises(ReferenceNotReadyError, match="no local CloneLab reference"):
        ref.retrieve(species="petunia", assembly="unknown", record_id="chr1", start=0, end=2)
