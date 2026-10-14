#!/usr/bin/env python3
"""Fetch the versioned JASPAR 2026 CORE plant PWM collection."""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "external_sources" / "JASPAR2026_CORE_plants.jaspar"
META = OUT.with_suffix(".metadata.json")
URL = (
    "https://jaspar.elixir.no/download/data/2026/CORE/"
    "JASPAR2026_CORE_plants_non-redundant_pfms_jaspar.txt"
)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    partial = OUT.with_suffix(OUT.suffix + ".part")
    request = urllib.request.Request(URL, headers={"User-Agent": "grn-atlas/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    partial.replace(OUT)
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    matrices = sum(1 for line in OUT.open(errors="replace") if line.startswith(">"))
    META.write_text(json.dumps({
        "source": "JASPAR", "release": "2026", "collection": "CORE plants non-redundant",
        "url": URL, "sha256": digest, "matrices": matrices,
    }, indent=2, sort_keys=True) + "\n")
    print(f"JASPAR 2026: {matrices} plant matrices -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
