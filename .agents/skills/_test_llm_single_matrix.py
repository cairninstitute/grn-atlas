#!/usr/bin/env python3
"""Per-case single-skill suite runner with stable output and pacing."""
import argparse
import json
import os
import time
from pathlib import Path

import _test_llm_single_skill as single

SKILLS_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Exhaustive single-skill matrix runner")
    parser.add_argument("--model", default=single.DEFAULT_MODEL)
    parser.add_argument("--http", default=None)
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between cases")
    parser.add_argument("--skill", default=None, help="Filter to one skill")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cases", default=str(SKILLS_DIR / "_test_llm_cases.json"))
    parser.add_argument("--out", default=str(SKILLS_DIR / "_test_results_llm_single_matrix.json"))
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: Set OPENROUTER_API_KEY")

    all_cases = json.loads(Path(args.cases).read_text())
    cases = all_cases
    if args.skill:
        cases = [c for c in cases if c["skill"] == args.skill]
    if args.limit is not None:
        cases = cases[: args.limit]

    results = []
    out_path = Path(args.out)

    for idx, tc in enumerate(cases, start=1):
        print(f"[{idx}/{len(cases)}] {tc['skill']}: {tc['label']}", flush=True)
        t0 = time.time()
        call = single.ask_for_tool_call(tc["question"], args.model, api_key)
        api_time = round(time.time() - t0, 1)
        tool_name = call.get("name")
        tool_args = call.get("args", {})
        err = call.get("error")
        tool_data = None
        if tool_name:
            tool_data = single._execute_full(tool_name, tool_args, args.http)

        check_results = []
        for check in tc["checks"]:
            desc, passed = single.evaluate_check(check, tool_name, tool_args, tool_data)
            check_results.append({"check": desc, "pass": passed})
        grade = "PASS" if check_results and all(c["pass"] for c in check_results) else "FAIL"
        result = {
            "skill": tc["skill"],
            "label": tc["label"],
            "question": tc["question"],
            "expected_tools": tc["expected_tools"],
            "actual_tool": tool_name,
            "tool_args": tool_args,
            "tool_correct": tool_name in tc["expected_tools"] if tool_name else False,
            "grade": grade,
            "checks": check_results,
            "api_time_s": api_time,
            "error": err,
        }
        results.append(result)
        out_path.write_text(json.dumps({"model": args.model, "results": results}, indent=2))
        mark = "✓" if grade == "PASS" else "✗"
        tool_mark = "✓" if result["tool_correct"] else "✗"
        print(f"  {mark} {grade} tool:{tool_mark} {tool_name or 'NONE'}({json.dumps(tool_args)[:120]}) [{api_time:.1f}s]", flush=True)
        if idx != len(cases):
            time.sleep(args.delay)

    passed = sum(r["grade"] == "PASS" for r in results)
    print(f"SUMMARY {passed}/{len(results)} PASS", flush=True)


if __name__ == "__main__":
    main()
