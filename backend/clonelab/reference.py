"""Versioned local reference registry for authenticated interval retrieval."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from Bio import SeqIO

from .sequence import canonical_sequence, reverse_complement, sequence_sha256


class ReferenceNotReadyError(ValueError):
    pass


class ReferenceRegistry:
    def __init__(self, manifest_path: str | Path):
        self.manifest_path = Path(manifest_path)
        if not self.manifest_path.exists():
            raise ReferenceNotReadyError(f"CloneLab reference manifest not found: {self.manifest_path}")
        payload = json.loads(self.manifest_path.read_text())
        self.entries = payload.get("references", [])
        self._records: dict[str, dict[str, str]] = {}

    def list(self) -> list[dict]:
        return [{key: value for key, value in entry.items() if key != "path"} for entry in self.entries]

    def retrieve(self, *, species: str, assembly: str, record_id: str,
                 start: int, end: int, strand: int = 1) -> dict:
        entry = next((item for item in self.entries if item["species"] == species and item["assembly"] == assembly), None)
        if not entry:
            raise ReferenceNotReadyError(f"no local CloneLab reference for {species} assembly {assembly}")
        records = self._load(entry)
        if record_id not in records:
            raise ReferenceNotReadyError(f"record {record_id} is absent from {species} {assembly}")
        parent = records[record_id]
        if not (0 <= start < end <= len(parent)):
            raise ValueError(f"interval [{start}, {end}) is outside record length {len(parent)}")
        sequence = parent[start:end]
        if strand == -1:
            sequence = reverse_complement(sequence)
        elif strand != 1:
            raise ValueError("strand must be 1 or -1")
        return {
            "species": species,
            "assembly": assembly,
            "record_id": record_id,
            "interval": {"start": start, "end": end, "strand": strand},
            "coordinate_system": "zero_based_half_open",
            "sequence": sequence,
            "length": len(sequence),
            "sequence_sha256": sequence_sha256(sequence),
            "reference_sha256": entry.get("sha256"),
            "source": entry.get("source"),
            "accession": entry.get("accession"),
        }

    def verify(self) -> list[dict]:
        results = []
        for entry in self.entries:
            path = self._path(entry)
            digest = _file_sha256(path) if path.exists() else None
            results.append({
                "species": entry["species"], "assembly": entry["assembly"],
                "path": str(path), "exists": path.exists(), "sha256": digest,
                "expected_sha256": entry.get("sha256"),
                "valid": path.exists() and (not entry.get("sha256") or digest == entry["sha256"]),
            })
        return results

    def _path(self, entry: dict) -> Path:
        path = Path(entry["path"])
        return path if path.is_absolute() else self.manifest_path.parent / path

    def _load(self, entry: dict) -> dict[str, str]:
        key = f"{entry['species']}:{entry['assembly']}"
        if key in self._records:
            return self._records[key]
        path = self._path(entry)
        if not path.exists():
            raise ReferenceNotReadyError(f"local reference file not found: {path}")
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as handle:
            records = {record.id: canonical_sequence(str(record.seq)) for record in SeqIO.parse(handle, "fasta")}
        self._records[key] = records
        return records


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
