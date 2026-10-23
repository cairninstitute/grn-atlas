#!/usr/bin/env python3
"""Run deterministic synthetic benchmarks for CloneLab digest optimization."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clonelab.diagnostics import optimize_digests


def molecule(length, sites):
    bases = ["C"] * length
    for start, site in sites.items():
        bases[start:start + len(site)] = site
    return "".join(bases)


def cases():
    orientation = [
        {"hypothesis_id": "intended", "sequence": molecule(1000, {100: "GAATTC", 300: "CTCGAG"}), "topology": "circular"},
        {"hypothesis_id": "reverse", "sequence": molecule(1000, {100: "GAATTC", 700: "CTCGAG"}), "topology": "circular"},
        {"hypothesis_id": "empty", "sequence": molecule(1000, {100: "GAATTC"}), "topology": "circular"},
    ]
    return [
        {"id": "orientation_and_presence", "hypotheses": orientation, "enzymes": ["EcoRI", "XhoI", "HindIII"], "expect_unique": True, "expected_best": {"EcoRI", "XhoI"}},
        {"id": "impossible_identical_states", "hypotheses": [orientation[0], {**orientation[0], "hypothesis_id": "duplicate"}], "enzymes": ["EcoRI", "XhoI"], "expect_unique": False, "expected_best": None},
        {"id": "single_enzyme_presence_only", "hypotheses": [orientation[0], orientation[2]], "enzymes": ["XhoI"], "expect_unique": True, "expected_best": {"XhoI"}},
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    rows = []
    for case in cases():
        result = optimize_digests(case["hypotheses"], case["enzymes"], min_fragment_bp=0, min_separation_bp=0, relative_resolution=0)
        best = set(result["best_digest"]["enzymes"])
        passed = (not result["no_unique_digest"]) == case["expect_unique"]
        if case["expected_best"] is not None:
            passed = passed and best == case["expected_best"]
        rows.append({
            "case_id": case["id"], "passed": passed,
            "best_digest": result["best_digest"]["enzymes"],
            "fully_discriminatory": result["best_digest"]["fully_discriminatory"],
            "no_unique_digest": result["no_unique_digest"],
        })
    payload = {
        "schema": "clonelab-diagnostic-benchmark-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark_class": "synthetic_known-truth",
        "claim_boundary": "These cases verify algorithm behavior; they are not an independent wet-lab or external-tool validation.",
        "passed": sum(row["passed"] for row in rows), "total": len(rows), "cases": rows,
    }
    text = json.dumps(payload, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    print(text, end="")
    raise SystemExit(0 if payload["passed"] == payload["total"] else 1)


if __name__ == "__main__":
    main()
