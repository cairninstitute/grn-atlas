"""Minimal samtools-compatible FASTA indexing and random-access retrieval."""

from __future__ import annotations

from pathlib import Path


def build_fasta_index(fasta_path: str | Path, index_path: str | Path | None = None) -> Path:
    fasta = Path(fasta_path)
    index = Path(index_path) if index_path else Path(f"{fasta}.fai")
    rows = []
    with fasta.open("rb") as handle:
        name = None
        length = 0
        sequence_offset = 0
        line_bases = 0
        line_width = 0

        def finish():
            if name is not None:
                if not line_bases:
                    raise ValueError(f"empty FASTA record: {name}")
                rows.append((name, length, sequence_offset, line_bases, line_width))

        while True:
            line_start = handle.tell()
            line = handle.readline()
            if not line:
                finish()
                break
            if line.startswith(b">"):
                finish()
                name = line[1:].split(None, 1)[0].decode("utf-8")
                length = 0
                sequence_offset = handle.tell()
                line_bases = 0
                line_width = 0
                continue
            bases = line.rstrip(b"\r\n")
            if name is None:
                raise ValueError(f"sequence data before FASTA header at byte {line_start}")
            if not line_bases:
                line_bases = len(bases)
                line_width = len(line)
            length += len(bases)
    index.write_text("".join("\t".join(map(str, row)) + "\n" for row in rows))
    return index


class IndexedFasta:
    def __init__(self, fasta_path: str | Path, index_path: str | Path | None = None):
        self.fasta_path = Path(fasta_path)
        self.index_path = Path(index_path) if index_path else Path(f"{self.fasta_path}.fai")
        if not self.index_path.exists():
            build_fasta_index(self.fasta_path, self.index_path)
        self.records = {}
        for line in self.index_path.read_text().splitlines():
            name, length, offset, line_bases, line_width = line.split("\t")[:5]
            self.records[name] = tuple(map(int, (length, offset, line_bases, line_width)))

    def length(self, record_id: str) -> int:
        try:
            return self.records[record_id][0]
        except KeyError as exc:
            raise KeyError(f"record {record_id} is absent from indexed FASTA") from exc

    def fetch(self, record_id: str, start: int, end: int) -> str:
        length, offset, line_bases, line_width = self.records.get(record_id, (None,) * 4)
        if length is None:
            raise KeyError(f"record {record_id} is absent from indexed FASTA")
        if not 0 <= start < end <= length:
            raise ValueError(f"interval [{start}, {end}) is outside record length {length}")
        byte_start = offset + (start // line_bases) * line_width + start % line_bases
        byte_end = offset + ((end - 1) // line_bases) * line_width + (end - 1) % line_bases + 1
        with self.fasta_path.open("rb") as handle:
            handle.seek(byte_start)
            raw = handle.read(byte_end - byte_start)
        sequence = raw.replace(b"\n", b"").replace(b"\r", b"").decode("ascii").upper()
        if len(sequence) != end - start:
            raise RuntimeError("indexed FASTA retrieval returned an unexpected sequence length")
        return sequence
