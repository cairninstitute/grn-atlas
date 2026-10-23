#!/usr/bin/env python3
"""Fetch approved PLAZA genomes, expand them, and build local random-access indexes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clonelab.indexed_fasta import build_fasta_index  # noqa: E402

DATA = ROOT / "data/clonelab/genomes"
MANIFEST = DATA / "genome_sources.json"
SOURCES = {
    "arabidopsis": {"code": "ath", "assembly": "TAIR10"},
    "petunia": {"code": "pax", "assembly": "Peaxi162v1.6.2"},
}
BASE = "https://ftp.psb.ugent.be/pub/plaza/plaza_public_dicots_05/Genomes"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", choices=["all", *SOURCES], default="all")
    args = parser.parse_args()
    selected = SOURCES if args.species == "all" else {args.species: SOURCES[args.species]}
    DATA.mkdir(parents=True, exist_ok=True)
    previous = json.loads(MANIFEST.read_text()).get("references", []) if MANIFEST.exists() else []
    rows = {row["species"]: row for row in previous}
    for species, source in selected.items():
        url = f"{BASE}/{source['code']}.fasta.gz"
        compressed = DATA / f"{source['code']}.fasta.gz"
        fasta = DATA / f"{source['code']}.fasta"
        if not compressed.exists():
            print(f"Downloading {species} genome from {url}")
            request = urllib.request.Request(url, headers={"User-Agent": "Darwin-CloneLab/0.2"})
            with urllib.request.urlopen(request, timeout=300) as response, compressed.open("wb") as target:
                shutil.copyfileobj(response, target, length=1024 * 1024)
        if not fasta.exists():
            print(f"Expanding {compressed.name}")
            with gzip.open(compressed, "rb") as source_handle, fasta.open("wb") as target:
                shutil.copyfileobj(source_handle, target, length=1024 * 1024)
        index = build_fasta_index(fasta)
        rows[species] = {
            "species": species, "assembly": source["assembly"], "source": "PLAZA Dicots 5.0",
            "url": url, "path": str(fasta.relative_to(ROOT / "data")),
            "index_path": str(index.relative_to(ROOT / "data")),
            "sha256": sha256(fasta), "compressed_sha256": sha256(compressed),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        print(f"Indexed {species}: {fasta.stat().st_size:,} bytes")
    MANIFEST.write_text(json.dumps({"schema": "clonelab-genome-sources-v1", "references": list(rows.values())}, indent=2) + "\n")


if __name__ == "__main__":
    main()
