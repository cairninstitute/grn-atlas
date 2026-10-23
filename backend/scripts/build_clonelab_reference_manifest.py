#!/usr/bin/env python3
"""Register locally available transcript FASTA files for CloneLab retrieval."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "clonelab_references.json"

REFERENCES = {
    "arabidopsis": ("TAIR10", "transcripts_arabidopsis.fasta.gz", "PLAZA Dicots 5.0 selected transcripts"),
    "petunia": ("Peaxi162v1.6.2", "transcripts_petunia.fasta.gz", "PLAZA Dicots 5.0 selected transcripts"),
    "tomato": ("SL4.0", "transcripts_tomato.fasta.gz", "PLAZA/SGN selected transcripts"),
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    rows = []
    for species, (assembly, filename, source) in REFERENCES.items():
        path = DATA / filename
        if not path.exists():
            continue
        rows.append({
            "species": species,
            "assembly": assembly,
            "molecule_type": "transcript",
            "path": filename,
            "sha256": sha256(path),
            "source": source,
            "accession": assembly,
        })
    genome_manifest = DATA / "clonelab/genomes/genome_sources.json"
    if genome_manifest.exists():
        for reference in json.loads(genome_manifest.read_text()).get("references", []):
            rows.append({
                "species": reference["species"], "assembly": reference["assembly"],
                "molecule_type": "genome", "path": reference["path"],
                "index_path": reference["index_path"], "sha256": reference["sha256"],
                "source": reference["source"], "accession": reference["assembly"],
                "url": reference["url"],
            })
    OUTPUT.write_text(json.dumps({"schema": "clonelab-reference-manifest-v1", "references": rows}, indent=2) + "\n")
    print(f"Wrote {OUTPUT} with {len(rows)} local references")


if __name__ == "__main__":
    main()
