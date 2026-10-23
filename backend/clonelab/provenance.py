"""Version and provenance records shared by CloneLab outputs."""

from __future__ import annotations

import platform

from Bio import __version__ as BIOPYTHON_VERSION

CLONELAB_ENGINE_VERSION = "0.1.0"


def engine_provenance() -> dict:
    return {
        "clonelab_engine": CLONELAB_ENGINE_VERSION,
        "biopython": BIOPYTHON_VERSION,
        "python": platform.python_version(),
        "coordinate_system": "zero_based_half_open_and_interbase_cuts",
    }
