#!/usr/bin/env python3
"""Compare CloneLab restriction calls with the independent EMBOSS engine."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from Bio import SeqIO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clonelab.external_validation import emboss_restriction_map  # noqa: E402
from clonelab.restriction import digest_sequence  # noqa: E402
from clonelab.sequence import sequence_sha256  # noqa: E402

DEFAULT_ENZYMES = ["EcoRI", "BamHI", "HindIII", "PstI", "SalI", "SmaI", "XbaI", "KpnI"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emboss-restrict", default=os.environ.get("EMBOSS_RESTRICT"))
    parser.add_argument("--emboss-root")
    parser.add_argument("--emboss-lib")
    parser.add_argument("--plasmid", default=ROOT / "data/clonelab/pUC19_L09137.2.gb", type=Path)
    parser.add_argument("--output", default=ROOT.parent / "docs/clonelab/validation/cross-tool-validation.json", type=Path)
    args = parser.parse_args()
    if not args.plasmid.exists():
        raise SystemExit("pUC19 fixture missing; run `make clonelab-data` first")

    record = SeqIO.read(args.plasmid, "genbank")
    sequence = str(record.seq).upper()
    environment = {}
    if args.emboss_root:
        environment["EMBOSS_ROOT"] = str(Path(args.emboss_root).resolve())
    if args.emboss_lib:
        environment["LD_LIBRARY_PATH"] = str(Path(args.emboss_lib).resolve())
    external = emboss_restriction_map(
        sequence, DEFAULT_ENZYMES, topology="circular",
        executable=args.emboss_restrict, environment=environment,
    )
    internal = digest_sequence(
        sequence, DEFAULT_ENZYMES, topology="circular", include_fragment_sequences=False
    )
    internal_sites = sorted(
        (row["enzyme"].lower(), row["recognition_start"], row["top_cut"])
        for row in internal["sites"]
    )
    external_sites = sorted(
        (row["enzyme"].lower(), row["recognition_start"], row["top_cut"])
        for row in external["sites"]
    )
    external_cuts = sorted({row["top_cut"] for row in external["sites"]})
    external_fragments = sorted(
        ((external_cuts[(index + 1) % len(external_cuts)] - cut) % len(sequence) or len(sequence)
         for index, cut in enumerate(external_cuts)),
        reverse=True,
    ) if external_cuts else []
    exact_sites = internal_sites == external_sites
    exact_fragments = internal["fragment_lengths"] == external_fragments
    payload = {
        "schema": "clonelab-cross-tool-validation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": {
            "name": "pUC19", "accession": record.id, "length": len(sequence),
            "sequence_sha256": sequence_sha256(sequence),
        },
        "enzymes": DEFAULT_ENZYMES,
        "internal_engine": internal["engine"],
        "external_engine": {key: external[key] for key in ("tool", "version")},
        "internal_sites": [{"enzyme": enzyme, "recognition_start": start, "top_cut": cut}
                           for enzyme, start, cut in internal_sites],
        "external_sites": [{"enzyme": enzyme, "recognition_start": start, "top_cut": cut}
                           for enzyme, start, cut in external_sites],
        "internal_fragment_lengths": internal["fragment_lengths"],
        "external_fragment_lengths": external_fragments,
        "exact_site_and_cut_match": exact_sites,
        "exact_fragment_match": exact_fragments,
        "exact_match": exact_sites and exact_fragments,
        "release_gate": "pass" if exact_sites and exact_fragments else "fail",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "release_gate": payload["release_gate"], "sites": len(internal_sites)}))
    return 0 if payload["exact_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
