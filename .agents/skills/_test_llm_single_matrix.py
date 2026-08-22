#!/usr/bin/env python3
"""Per-case single-skill suite runner with stable output and pacing."""
import argparse
import json
import os
import time
from pathlib import Path
import urllib.request

import _test_llm_single_skill as single

SKILLS_DIR = Path(__file__).resolve().parent


def _default_case_paths() -> list[Path]:
    base = SKILLS_DIR / "_test_llm_cases.json"
    supp = sorted(SKILLS_DIR.glob("_test_llm_cases_*.json"))
    paths = [base]
    for p in supp:
        if p != base:
            paths.append(p)
    return paths


def _resolve_field(data, field):
    parts = field.split(".")
    obj = data
    for p in parts:
        if obj is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(p)
        elif isinstance(obj, list):
            try:
                obj = obj[int(p)]
            except Exception:
                return None
        else:
            return None
    return obj


def _fmt(value, context):
    if isinstance(value, str):
        try:
            return value.format(**context)
        except Exception:
            return value
    if isinstance(value, list):
        return [_fmt(v, context) for v in value]
    if isinstance(value, dict):
        return {k: _fmt(v, context) for k, v in value.items()}
    return value


def _load_cases(cases_arg: str):
    if cases_arg.strip().lower() == "auto":
        paths = [str(p) for p in _default_case_paths()]
    else:
        paths = [p.strip() for p in cases_arg.split(",") if p.strip()]
    cases = []
    for p in paths:
        cases.extend(json.loads(Path(p).read_text()))
    return cases


def _http_post(base_url: str, path: str, payload: dict):
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _prepare_case(tc: dict, http_url: str | None):
    context = {}
    if tc.get("setup_http_posts"):
        if not http_url:
            return None, {"grade": "SKIP", "error": "requires_http_setup"}
        for step in tc["setup_http_posts"]:
            payload = _fmt(step["json"], context)
            data = _http_post(http_url, step["path"], payload)
            for key, field in step.get("capture", {}).items():
                context[key] = _resolve_field(data, field)
    prepared = _fmt(tc, context)
    return prepared, None


def main():
    parser = argparse.ArgumentParser(description="Exhaustive single-skill matrix runner")
    parser.add_argument("--model", default=single.DEFAULT_MODEL)
    parser.add_argument("--provider", default="auto", choices=["auto", "openrouter", "openai"])
    parser.add_argument("--http", default=None)
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between cases")
    parser.add_argument("--retries", type=int, default=1, help="Retries after the first attempt for non-pass cases")
    parser.add_argument("--skill", default=None, help="Filter to one skill")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--cases", default="auto")
    parser.add_argument("--out", default=str(SKILLS_DIR / "_test_results_llm_single_matrix.json"))
    args = parser.parse_args()

    provider = single.resolve_provider(args.model, args.provider)
    api_key = single.get_api_key(provider)
    if not api_key:
        env_name = "OPENAI_API_KEY" if provider == "openai" else "OPENROUTER_API_KEY"
        raise SystemExit(f"ERROR: Set {env_name}")

    all_cases = _load_cases(args.cases)
    cases = all_cases
    if args.skill:
        cases = [c for c in cases if c["skill"] == args.skill]
    if args.limit is not None:
        cases = cases[: args.limit]

    results = []
    out_path = Path(args.out)

    for idx, tc in enumerate(cases, start=1):
        print(f"[{idx}/{len(cases)}] {tc['skill']}: {tc['label']}", flush=True)
        prepared_case, prep_error = _prepare_case(tc, args.http)
        if prep_error:
            result = {
                "skill": tc["skill"],
                "label": tc["label"],
                "question": tc["question"],
                "expected_tools": tc["expected_tools"],
                "actual_tool": None,
                "tool_args": {},
                "tool_correct": False,
                "grade": "SKIP",
                "checks": [],
                "api_time_s": 0.0,
                "error": prep_error["error"],
                "error_category": prep_error["error"],
                "failure_mode": "skipped_requires_http",
                "attempt": 0,
            }
            results.append(result)
            out_path.write_text(json.dumps({"model": args.model, "results": results}, indent=2))
            continue
        tc = prepared_case
        attempts = []
        for attempt in range(1, args.retries + 2):
            t0 = time.time()
            call = single.ask_for_tool_call(tc["question"], args.model, api_key, provider=provider)
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
                "error_category": single.classify_error(err),
                "failure_mode": single.classify_failure_mode(tool_name, tc["expected_tools"], err, grade),
                "attempt": attempt,
            }
            attempts.append(result)
            mark = "✓" if grade == "PASS" else "✗"
            tool_mark = "✓" if result["tool_correct"] else "✗"
            print(f"  {mark} {grade} tool:{tool_mark} {tool_name or 'NONE'}({json.dumps(tool_args)[:120]}) [{api_time:.1f}s] attempt {attempt}", flush=True)
            if grade == "PASS":
                break
            if attempt < args.retries + 1:
                time.sleep(args.delay)

        final = attempts[-1].copy()
        final["attempts"] = attempts
        final["flaky_pass"] = len(attempts) > 1 and final["grade"] == "PASS" and any(a["grade"] != "PASS" for a in attempts[:-1])
        results.append(final)
        out_path.write_text(json.dumps({"model": args.model, "results": results}, indent=2))
        if idx != len(cases):
            time.sleep(args.delay)

    passed = sum(r["grade"] == "PASS" for r in results)
    skipped = sum(r["grade"] == "SKIP" for r in results)
    flaky = sum(1 for r in results if r.get("flaky_pass"))
    failure_modes = {}
    for r in results:
        if r["grade"] not in ("PASS", "SKIP"):
            key = r.get("failure_mode") or "unknown_failure"
            failure_modes[key] = failure_modes.get(key, 0) + 1
    print(f"SUMMARY {passed}/{len(results)} PASS skipped={skipped} flaky_pass={flaky} failure_modes={failure_modes}", flush=True)


if __name__ == "__main__":
    main()
