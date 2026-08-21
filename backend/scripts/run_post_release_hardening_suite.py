from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from validation_common import RUNS_DIR, corpus_manifest, ensure_runs_dir, git_sha

SCRIPTS = [
    "benchmark_tf_activity.py",
    "benchmark_pathway_activity.py",
    "benchmark_celltype_regulation.py",
    "benchmark_trajectory_workflows.py",
    "benchmark_signaling_to_tf.py",
    "benchmark_rnai_comparator.py",
    "benchmark_crispr_comparator.py",
    "benchmark_species_gold_standards.py",
]


def run_script(script: str) -> dict:
    cmd = [sys.executable, str(Path(__file__).resolve().parent / script)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "status": "pass" if proc.returncode == 0 else "fail",
    }


def load_outputs() -> list[dict]:
    payloads = []
    for path in sorted(RUNS_DIR.glob("benchmark_*.json")):
        try:
            payload = json.loads(path.read_text())
        except Exception as exc:
            payload = {"benchmark": path.stem, "status": "fail", "error": str(exc)}
        milestone = payload.get("milestone", "")
        if milestone.startswith("PR") or payload.get("benchmark") in {
            "benchmark_tf_activity",
            "benchmark_pathway_activity",
            "benchmark_celltype_regulation",
            "benchmark_trajectory_workflows",
            "benchmark_signaling_to_tf",
            "benchmark_rnai_comparator",
            "benchmark_crispr_comparator",
            "benchmark_species_gold_standards",
        }:
            payloads.append(payload)
    return payloads


def write_summary(summary: dict) -> None:
    ensure_runs_dir()
    (RUNS_DIR / "post_release_hardening_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Post-release hardening summary",
        "",
        f"- run_at_utc: {summary['run_at_utc']}",
        f"- suite_status: {summary['suite_status']}",
        f"- scripts_run: {len(summary['script_runs'])}",
        f"- benchmark_files: {len(summary['benchmarks'])}",
        "",
        "## Script runs",
        "",
    ]
    for run in summary["script_runs"]:
        lines.append(f"- `{run['script']}` — {run['status']} (rc={run['returncode']})")
    lines.extend(["", "## Benchmark statuses", ""])
    for bm in summary["benchmarks"]:
        lines.append(f"- `{bm.get('benchmark')}` — {bm.get('status')} ({bm.get('milestone', 'n/a')})")
    (RUNS_DIR / "post_release_hardening_summary.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ensure_runs_dir()
    script_runs = [run_script(script) for script in SCRIPTS]
    validator = run_script("validate_validation_artifacts.py")
    script_runs.append(validator)
    summary = {
        "schema_version": "1.0",
        "git_sha": git_sha(),
        "benchmark_corpus_version": corpus_manifest().get("corpus_version", "unknown"),
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "suite_status": "pass" if all(run["returncode"] == 0 for run in script_runs) else "fail",
        "script_runs": script_runs,
        "benchmarks": load_outputs(),
        "scope": "post_release_hardening_pr1_pr7",
    }
    write_summary(summary)
    print(RUNS_DIR / "post_release_hardening_summary.json")


if __name__ == "__main__":
    main()
