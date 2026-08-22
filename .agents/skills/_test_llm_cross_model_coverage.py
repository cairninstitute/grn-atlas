#!/usr/bin/env python3
"""Run single-skill and orchestration matrices for GPT-5.4 and Nemotron, then summarize coverage."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable

MODELS = {
    "gpt-5.4": {"model": "gpt-5.4", "provider": "openai"},
    "nemotron-3-ultra": {"model": "nvidia/nemotron-3-ultra-550b-a55b:free", "provider": "openrouter"},
}


def run(cmd: list[str]) -> int:
    proc = subprocess.run(cmd, cwd=str(SKILLS_DIR.parents[1]))
    return proc.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-model LLM coverage runner")
    parser.add_argument("--http", default=None, help="Backend base URL; strongly recommended for import-dependent skills")
    parser.add_argument("--single-cases", default=f"{SKILLS_DIR / '_test_llm_cases.json'},{SKILLS_DIR / '_test_llm_cases_supplemental_2026-08-21.json'}")
    parser.add_argument("--out", default=str(SKILLS_DIR / "_test_results_llm_cross_model_coverage.json"))
    parser.add_argument("--single-retries", type=int, default=1)
    parser.add_argument("--orch-retries", type=int, default=1)
    parser.add_argument("--single-delay", type=float, default=3.0)
    parser.add_argument("--orch-timeout", type=int, default=420)
    args = parser.parse_args()

    summary: dict[str, object] = {"models": {}}
    for label, spec in MODELS.items():
        single_out = SKILLS_DIR / f"_test_results_{label.replace('.', '').replace('-', '_')}_single_coverage.json"
        orch_out = SKILLS_DIR / f"_test_results_{label.replace('.', '').replace('-', '_')}_orch_coverage.json"

        single_cmd = [
            PYTHON, str(SKILLS_DIR / "_test_llm_single_matrix.py"),
            "--model", spec["model"],
            "--provider", spec["provider"],
            "--cases", args.single_cases,
            "--retries", str(args.single_retries),
            "--delay", str(args.single_delay),
            "--out", str(single_out),
        ]
        orch_cmd = [
            PYTHON, str(SKILLS_DIR / "_test_llm_orchestration_matrix.py"),
            "--model", spec["model"],
            "--provider", spec["provider"],
            "--retries", str(args.orch_retries),
            "--timeout", str(args.orch_timeout),
            "--out", str(orch_out),
        ]
        if args.http:
            single_cmd += ["--http", args.http]
            orch_cmd += ["--http", args.http]

        summary["models"][label] = {
            "single_cmd": single_cmd,
            "orch_cmd": orch_cmd,
            "single_rc": run(single_cmd),
            "orch_rc": run(orch_cmd),
            "single_out": str(single_out),
            "orch_out": str(orch_out),
        }

    Path(args.out).write_text(json.dumps(summary, indent=2) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
