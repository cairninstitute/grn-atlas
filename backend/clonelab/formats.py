"""FASTA and GenBank import/export adapters."""

from __future__ import annotations

from io import StringIO

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from .sequence import canonical_sequence, normalize_topology


def detect_format(content: str) -> str:
    stripped = (content or "").lstrip()
    if stripped.startswith(">"):
        return "fasta"
    if stripped.startswith("LOCUS"):
        return "genbank"
    raise ValueError("could not detect sequence format; expected FASTA or GenBank text")


def _feature_to_dict(feature: SeqFeature) -> dict:
    parts = feature.location.parts if isinstance(feature.location, CompoundLocation) else [feature.location]
    return {
        "type": feature.type,
        "start": int(feature.location.start),
        "end": int(feature.location.end),
        "strand": feature.location.strand,
        "parts": [
            {"start": int(part.start), "end": int(part.end), "strand": part.strand}
            for part in parts
        ],
        "qualifiers": {key: list(value) for key, value in feature.qualifiers.items()},
    }


def parse_sequences(
    content: str,
    *,
    file_format: str = "auto",
    default_topology: str = "linear",
    source: str | None = None,
) -> list[dict]:
    selected_format = detect_format(content) if file_format == "auto" else file_format.lower()
    if selected_format not in {"fasta", "genbank"}:
        raise ValueError("file_format must be auto, fasta, or genbank")
    records = list(SeqIO.parse(StringIO(content), selected_format))
    if not records:
        raise ValueError(f"no sequence records found in {selected_format} input")
    out = []
    for record in records:
        topology = normalize_topology(record.annotations.get("topology", default_topology))
        sequence = canonical_sequence(str(record.seq))
        accessions = record.annotations.get("accessions") or []
        accession = accessions[0] if accessions else (record.id if record.id != "<unknown id>" else None)
        out.append({
            "name": record.name if record.name != "<unknown name>" else record.id,
            "description": record.description,
            "sequence": sequence,
            "topology": topology,
            "accession": accession,
            "source": source,
            "features": [_feature_to_dict(feature) for feature in record.features],
            "annotations": {
                key: value for key, value in record.annotations.items()
                if isinstance(value, (str, int, float, bool, list, dict))
            },
            "format": selected_format,
        })
    return out


def _dict_to_feature(data: dict) -> SeqFeature:
    parts = data.get("parts") or []
    if len(parts) > 1:
        location = CompoundLocation([
            FeatureLocation(part["start"], part["end"], strand=part.get("strand"))
            for part in parts
        ])
    else:
        location = FeatureLocation(data["start"], data["end"], strand=data.get("strand"))
    return SeqFeature(
        location=location,
        type=data.get("type", "misc_feature"),
        qualifiers=data.get("qualifiers") or {},
    )


def export_fasta(record: dict) -> str:
    seq_record = SeqRecord(
        Seq(canonical_sequence(record["sequence"])),
        id=record.get("accession") or record.get("sequence_id") or record.get("name") or "sequence",
        name=record.get("name") or "sequence",
        description=record.get("description") or "",
    )
    handle = StringIO()
    SeqIO.write(seq_record, handle, "fasta")
    return handle.getvalue()


def export_genbank(record: dict) -> str:
    sequence = canonical_sequence(record["sequence"])
    seq_record = SeqRecord(
        Seq(sequence),
        id=record.get("accession") or record.get("sequence_id") or record.get("name") or "sequence",
        name=(record.get("name") or "sequence")[:16],
        description=record.get("description") or "",
    )
    annotations = dict(record.get("annotations") or {})
    annotations["molecule_type"] = "DNA"
    annotations["topology"] = normalize_topology(record.get("topology", "linear"))
    seq_record.annotations = annotations
    seq_record.features = [_dict_to_feature(feature) for feature in record.get("features", [])]
    handle = StringIO()
    SeqIO.write(seq_record, handle, "genbank")
    return handle.getvalue()
