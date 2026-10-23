"""Deterministic molecular analysis engine for Darwin CloneLab.

The public functions are intentionally independent of FastAPI and the atlas database.
"""

from .assembly import assemble_insert
from .diagnostics import optimize_digests
from .formats import export_fasta, export_genbank, parse_sequences
from .gel import simulate_gel
from .hypotheses import construct_hypotheses
from .interpretation import interpret_bands
from .reports import export_report
from .restriction import digest_sequence, ends_compatible, restriction_map
from .sequence import canonical_sequence, molecule_sha256, reverse_complement, sequence_sha256
from .workflow import optimize_construct_design

__all__ = [
    "assemble_insert",
    "canonical_sequence",
    "construct_hypotheses",
    "digest_sequence",
    "ends_compatible",
    "export_fasta",
    "export_genbank",
    "export_report",
    "interpret_bands",
    "molecule_sha256",
    "optimize_digests",
    "optimize_construct_design",
    "parse_sequences",
    "restriction_map",
    "reverse_complement",
    "sequence_sha256",
    "simulate_gel",
]
