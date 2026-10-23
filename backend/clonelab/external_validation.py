"""Independent restriction analysis through the EMBOSS ``restrict`` executable."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .sequence import canonical_sequence


class ExternalToolUnavailable(RuntimeError):
    """Raised when the requested independent validation tool is unavailable."""


def find_emboss_restrict(explicit: str | Path | None = None) -> Path:
    candidates = [explicit, os.environ.get("EMBOSS_RESTRICT"), shutil.which("restrict")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise ExternalToolUnavailable(
        "EMBOSS restrict was not found; install the emboss package or set EMBOSS_RESTRICT"
    )


def emboss_restriction_map(
    sequence: str,
    enzymes: list[str],
    *,
    topology: str = "circular",
    executable: str | Path | None = None,
    environment: dict[str, str] | None = None,
) -> dict:
    """Run EMBOSS and normalize its one-based report positions to zero-based cuts."""
    if topology not in {"linear", "circular"}:
        raise ValueError("topology must be linear or circular")
    if not enzymes:
        raise ValueError("at least one enzyme is required")
    bases = canonical_sequence(sequence)
    binary = find_emboss_restrict(executable)
    env = {**os.environ, **(environment or {})}
    with tempfile.TemporaryDirectory(prefix="clonelab-emboss-") as directory:
        fasta = Path(directory) / "input.fa"
        report = Path(directory) / "output.restrict"
        fasta.write_text(f">query\n{bases}\n")
        command = [
            str(binary), "-sequence", str(fasta), "-outfile", str(report),
            "-enzymes", ",".join(enzymes), "-sitelen", "2", "-min", "1",
            "-max", "2000000000", "-nolimit", "-auto",
        ]
        if topology == "circular":
            command.append("-plasmid")
        completed = subprocess.run(command, env=env, text=True, capture_output=True, timeout=60)
        if completed.returncode != 0:
            raise RuntimeError(f"EMBOSS restrict failed: {completed.stderr.strip()}")
        output = report.read_text()
        version_result = subprocess.run(
            [str(binary), "-version"], env=env, text=True, capture_output=True, timeout=10
        )
        version = (version_result.stdout or version_result.stderr).strip()

    sites = []
    # EMBOSS table rows begin with start/end coordinates followed by enzyme name.
    for line in output.splitlines():
        match = re.match(
            r"^\s*(\d+)\s+(\d+)\s+[+-]\s+([A-Za-z0-9._-]+)\s+\S+\s+(\d+)\s+", line
        )
        if not match:
            continue
        start, _end, enzyme, top_cut = match.groups()
        if enzyme.lower() not in {value.lower() for value in enzymes}:
            continue
        sites.append({
            "enzyme": enzyme, "recognition_start": int(start) - 1,
            "top_cut": int(top_cut) % len(bases) if topology == "circular" else int(top_cut),
        })
    return {
        "tool": "EMBOSS restrict",
        "version": version or "unknown",
        "topology": topology,
        "sequence_length": len(bases),
        "sites": sorted(sites, key=lambda row: (row["top_cut"], row["enzyme"].lower())),
        "raw_report": output,
    }
