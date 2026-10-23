#!/usr/bin/env python3
"""Fetch small, approved CloneLab reference records with identity checks."""

import hashlib
import json
import urllib.request
from pathlib import Path

from Bio import SeqIO

DATA = Path(__file__).resolve().parents[1] / "data" / "clonelab"
MANIFEST = DATA / "reference_plasmids.json"
REFERENCES = [{
    "name": "pUC19",
    "accession": "L09137.2",
    "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=L09137.2&rettype=gbwithparts&retmode=text",
    "filename": "pUC19_L09137.2.gb",
    "length": 2686,
    "sequence_sha256": "8a205af08518dae1b0045c7b098986dca18824ef654e75233603602ab89cad04",
    "source": "NCBI Nucleotide",
    "license_notes": "NCBI sequence record; retain accession and source attribution.",
}]


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    rows = []
    for reference in REFERENCES:
        path = DATA / reference["filename"]
        if not path.exists():
            with urllib.request.urlopen(reference["url"], timeout=60) as response:
                path.write_bytes(response.read())
        record = SeqIO.read(path, "genbank")
        sequence = str(record.seq).upper()
        digest = hashlib.sha256(sequence.encode("ascii")).hexdigest()
        if len(sequence) != reference["length"] or digest != reference["sequence_sha256"]:
            path.unlink(missing_ok=True)
            raise RuntimeError(f"identity check failed for {reference['accession']}")
        rows.append({**reference, "path": str(path.relative_to(DATA.parent))})
        print(f"Verified {reference['name']} {reference['accession']}: {len(sequence)} bp")
    MANIFEST.write_text(json.dumps({"schema": "clonelab-plasmid-manifest-v1", "references": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
