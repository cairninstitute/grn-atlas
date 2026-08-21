from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from validation_common import DATA_DIR, RUNS_DIR, ensure_runs_dir

SCRIPTS = [
    "validate_regulation_quality.py",
    "validate_network_statistics.py",
    "benchmark_beeline.py",
    "benchmark_tf_activity.py",
    "benchmark_pathway_activity.py",
    "benchmark_omics_import.py",
    "benchmark_celltype_regulation.py",
    "benchmark_chromatin_support.py",
    "benchmark_trajectory_workflows.py",
    "benchmark_rnai_design.py",
    "benchmark_crispr_design.py",
    "benchmark_perturbation_calibration.py",
    "benchmark_signaling_to_tf.py",
    "benchmark_transferability.py",
    "benchmark_workflow_packaging.py",
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


def load_benchmark_outputs() -> list[dict]:
    out = []
    for path in sorted(RUNS_DIR.glob("benchmark_*.json")):
        try:
            payload = json.loads(path.read_text())
        except Exception as exc:
            payload = {"benchmark": path.stem, "status": "fail", "error": str(exc)}
        out.append(payload)
    return out


def write_summary(summary: dict) -> None:
    ensure_runs_dir()
    (RUNS_DIR / "latest_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Validation suite summary",
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
        lines.append(f"- `{bm.get('benchmark')}` — {bm.get('status')}")
    (RUNS_DIR / "latest_summary.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ensure_runs_dir()
    script_runs = [run_script(script) for script in SCRIPTS]
    suite_status = "pass" if all(run["returncode"] == 0 for run in script_runs) else "fail"
    summary = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "suite_status": suite_status,
        "script_runs": script_runs,
        "benchmarks": load_benchmark_outputs(),
        "legacy_artifacts": {
            "quality_reports": [str(DATA_DIR / "quality_report_petunia.json"), str(DATA_DIR / "quality_report_tomato.json")],
            "network_report": str(DATA_DIR / "network_validation_report.md"),
            "beeline_report": str(DATA_DIR / "beeline_benchmark_report.json"),
        },
    }
    write_summary(summary)
    print(RUNS_DIR / "latest_summary.json")


if __name__ == "__main__":
    main()
