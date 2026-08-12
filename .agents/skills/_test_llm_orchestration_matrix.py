#!/usr/bin/env python3
"""Per-question orchestration suite runner with isolation and retries."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import _test_llm_orchestration as orch

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]


def run_one(question_id: int, timeout_s: int, env: dict[str, str]) -> dict:
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(SKILLS_DIR / "_test_llm_orchestration.py"), "--question", str(question_id)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(REPO_ROOT),
            env=env,
        )
        elapsed = round(time.time() - t0, 1)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        if "Results: 1/1 PASS" in stdout:
            grade = "PASS"
        elif "Results: 0/1 PASS" in stdout:
            grade = "FAIL"
        elif proc.returncode != 0:
            grade = "ERROR"
        else:
            grade = "UNKNOWN"
        return {
            "question_id": question_id,
            "grade": grade,
            "returncode": proc.returncode,
            "elapsed_s": elapsed,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired as e:
        elapsed = round(time.time() - t0, 1)
        return {
            "question_id": question_id,
            "grade": "TIMEOUT",
            "returncode": None,
            "elapsed_s": elapsed,
            "stdout": e.stdout or "",
            "stderr": e.stderr or "",
        }


def main():
    parser = argparse.ArgumentParser(description="Exhaustive isolated orchestration runner")
    parser.add_argument("--retries", type=int, default=1, help="Retries after the first attempt for non-pass cases")
    parser.add_argument("--timeout", type=int, default=420, help="Per-question timeout in seconds")
    parser.add_argument("--sleep-between", type=float, default=0.0, help="Sleep between questions to avoid rate limits")
    parser.add_argument("--out", default=str(SKILLS_DIR / "_test_results_llm_orchestration_matrix.json"))
    parser.add_argument("--question", type=int, default=None, help="Run only one question id")
    args = parser.parse_args()

    question_ids = [args.question] if args.question else list(range(1, len(orch.QUESTIONS) + 1))
    env = os.environ.copy()
    results = []
    out_path = Path(args.out)

    for qid in question_ids:
        attempts = []
        for attempt in range(1, args.retries + 2):
            print(f"Q{qid}/{len(question_ids) if args.question else len(orch.QUESTIONS)} attempt {attempt} start", flush=True)
            res = run_one(qid, args.timeout, env)
            res["attempt"] = attempt
            attempts.append(res)
            print(f"Q{qid} attempt {attempt} {res['grade']} {res['elapsed_s']}s", flush=True)
            if res["grade"] == "PASS":
                break
        final = attempts[-1].copy()
        final["attempts"] = attempts
        final["flaky_pass"] = len(attempts) > 1 and any(a["grade"] != "PASS" for a in attempts[:-1]) and final["grade"] == "PASS"
        results.append(final)
        out_path.write_text(json.dumps(results, indent=2))
        if args.sleep_between and qid != question_ids[-1]:
            time.sleep(args.sleep_between)

    summary = {}
    for r in results:
        summary[r["grade"]] = summary.get(r["grade"], 0) + 1
    flaky = sum(1 for r in results if r.get("flaky_pass"))
    print(f"SUMMARY {summary} total={len(results)} flaky_pass={flaky}", flush=True)


if __name__ == "__main__":
    main()
