#!/usr/bin/env python3
"""Run and publish the feedback-control verification gate."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from feedback_verification import run_verification  # noqa: E402


def markdown_report(result: dict) -> str:
    structural = result["structural_truth"]
    biological = result["biological_recovery"]
    lines = [
        "# Feedback-control verification report",
        "",
        f"**Status: {result['status'].upper()}**",
        "",
        "## Acceptance gates",
        "",
        "| Gate | Result |",
        "| --- | --- |",
    ]
    lines.extend(
        f"| {name.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |"
        for name, passed in result["gates"].items()
    )
    lines.extend([
        "",
        "## Independent structural truth",
        "",
        f"NetworkX exhaustive enumeration was used on {structural['fixture_count']} small signed graphs. "
        "Production-scale cycle output remains explicitly bounded.",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Feedback-core recall | {structural['core_recall']:.1%} |",
        f"| Feedback-core precision | {structural['core_precision']:.1%} |",
        f"| Signed-cycle recall through length 6 | {structural['cycle_recall']:.1%} |",
        f"| Signed-cycle precision through length 6 | {structural['cycle_precision']:.1%} |",
        f"| Cycle-polarity accuracy | {structural['polarity_accuracy']:.1%} |",
        f"| Exact FVS optimality | {structural['exact_fvs_optimal_rate']:.1%} |",
        f"| Greedy FVS mean size / optimum | {structural['greedy_fvs_mean_size_ratio']:.3f}x |",
        f"| Greedy FVS worst size / optimum | {structural['greedy_fvs_max_size_ratio']:.2f}x |",
        "",
        "## Biological recovery",
        "",
        "| Reference circuit | Atlas coverage | Core | Signed circuit | Attribution |",
        "| --- | --- | --- | --- | --- |",
    ])
    for row in biological["reference_circuits"]:
        lines.append(
            f"| {row['name']} | {'complete' if row['edge_coverage_complete'] else 'incomplete'} "
            f"| {'yes' if row['core_recovered'] else 'no'} | {'yes' if row['circuit_recovered'] else 'no'} "
            f"| {row['attribution']} |"
        )
    clock = biological["arabidopsis_clock_architecture"]
    lines.extend([
        "",
        "### Arabidopsis clock coverage",
        "",
        f"The atlas supports {clock['supported_arms']} of {clock['total_arms']} required module-level arms. "
        f"A closed three-module loop is {'recoverable' if clock['closed_three_module_loop_recoverable'] else 'not recoverable'} "
        "from the current signed edges alone.",
        "",
    ])
    for arm in clock["arms"]:
        lines.append(f"- {'Supported' if arm['supported'] else 'Missing'}: {arm['name']}")
    lines.extend([
        "",
        "## Robustness",
        "",
        "| Case | Nodes | Edges | Seconds | Truncation explicit |",
        "| --- | ---: | ---: | ---: | --- |",
    ])
    for row in result["robustness"]["cases"]:
        lines.append(
            f"| {row['name']} | {row['nodes']:,} | {row['edges']:,} | {row['seconds']:.4f} "
            f"| {'yes' if any(row['truncation'].values()) else 'not needed'} |"
        )
    lines.extend([
        "",
        "## Scores and persistence",
        "",
        f"- Score ordering checks: {'PASS' if result['gates']['score_behavior_consistent'] else 'FAIL'}",
        "- Score interpretation: heuristic ranking, not a calibrated probability",
        f"- Cache invalidation and normalized persistence: "
        f"{'PASS' if result['gates']['persistence_consistent'] else 'FAIL'}",
    ])
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {limitation}" for limitation in result["limitations"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=BACKEND / "data" / "grn.sqlite3")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    with sqlite3.connect(args.database) as conn:
        result = run_verification(conn)
    print(json.dumps({"status": result["status"], "gates": result["gates"]}, indent=2))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + "\n")
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="") as handle:
            fields = ["name", "species", "expected_family", "expected_polarity",
                      "edge_coverage_complete", "core_recovered", "circuit_recovered", "attribution"]
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows({key: row[key] for key in fields}
                             for row in result["biological_recovery"]["reference_circuits"])
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown_report(result))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
