#!/usr/bin/env python3
"""
Single-skill LLM test harness for GRN Atlas.

For each ground-truth test case, converts the test into a natural language
question, asks the LLM to pick the right tool and arguments, executes
the skill, and grades the output against ground truth.

Usage:
    export OPENROUTER_API_KEY=sk-or-...
    export OPENAI_API_KEY=sk-...
    backend/venv/bin/python .agents/skills/_test_llm_single_skill.py [options]

Options:
    --model MODEL_ID    Model id (default: nvidia/nemotron-3-ultra-550b-a55b:free)
    --provider NAME     auto | openrouter | openai
    --http URL          Pass through to skills
    --verbose           Print tool calls and results
    --skill SKILL       Run only tests for this skill (e.g. grn-network)
    --limit N           Run only first N tests
    --delay SECS        Delay between API calls (default: 1.0 for free tier)
    --resume FILE       Resume from a partial results file
    --cases FILE        Test cases JSON file (default: _test_llm_cases.json)
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
PYTHON = str(REPO_ROOT / "backend" / "venv" / "bin" / "python")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
API_RETRIES = 6
API_BACKOFF_S = 5
API_TIMEOUT_S = 180

sys.path.insert(0, str(SKILLS_DIR))
from _test_llm_orchestration import TOOLS, execute_tool, SYSTEM_PROMPT, _tool_to_cli, resolve_provider, get_api_key


def classify_error(err: str | None) -> str | None:
    if not err:
        return None
    txt = str(err).lower()
    if "upstream idle timeout exceeded" in txt or "timed out" in txt or "timeout" in txt:
        return "provider_timeout"
    if "internal server error" in txt or "upstream error from nvidia" in txt:
        return "provider_internal"
    if "rate_limited" in txt or "rate limit" in txt or "too many requests" in txt or "429" in txt:
        return "provider_rate_limit"
    if "http error 404" in txt:
        return "backend_404"
    if "http error 502" in txt or "bad gateway" in txt:
        return "backend_502"
    if "http error" in txt:
        return "backend_http"
    if err == "no_tool_call":
        return "no_tool_call"
    return "other_error"


def classify_failure_mode(tool_name: str | None, expected_tools: list[str], err: str | None, grade: str) -> str | None:
    if grade == "PASS":
        return None
    category = classify_error(err)
    if category:
        return category
    if tool_name and expected_tools and tool_name not in expected_tools:
        return "wrong_tool"
    if tool_name and expected_tools and tool_name in expected_tools:
        return "right_tool_bad_args_or_data"
    if not tool_name:
        return "no_tool_call"
    return "unknown_failure"


def _execute_full(tool_name: str, args: dict, http_url: str | None):
    """Execute a tool without output truncation, for grading."""
    cmd = _tool_to_cli(tool_name, args, http_url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(REPO_ROOT))
        if proc.returncode != 0:
            return None
        return json.loads(proc.stdout)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Check evaluators — driven by JSON check descriptors
# ---------------------------------------------------------------------------

def _resolve_field(data, field):
    """Resolve a dotted field path like 'results.0.symbol' or a simple field."""
    if data is None:
        return None
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
            except (IndexError, ValueError):
                return None
        else:
            return None
    return obj


def evaluate_check(check: dict, tool_name: str | None, tool_args: dict, tool_data) -> tuple[str, bool]:
    """Evaluate a single check descriptor. Returns (description, passed)."""
    ct = check["type"]

    if ct == "tool_in":
        tools = check["tools"]
        desc = f"tool in {tools}"
        return desc, tool_name in tools

    elif ct == "arg_equals":
        arg, val = check["arg"], check["value"]
        actual = tool_args.get(arg)
        desc = f"arg {arg}={val}"
        if isinstance(val, str) and isinstance(actual, str):
            return desc, actual.lower() == val.lower()
        return desc, actual == val

    elif ct == "arg_contains":
        arg, val = check["arg"], check["value"]
        actual = str(tool_args.get(arg, ""))
        desc = f"arg {arg} contains {val}"
        return desc, val.upper() in actual.upper()

    elif ct == "arg_gte":
        arg, val = check["arg"], check["value"]
        actual = tool_args.get(arg)
        desc = f"arg {arg} >= {val}"
        if actual is None:
            return desc, False
        return desc, float(actual) >= float(val)

    elif ct == "arg_lte":
        arg, val = check["arg"], check["value"]
        actual = tool_args.get(arg)
        desc = f"arg {arg} <= {val}"
        if actual is None:
            return desc, False
        return desc, float(actual) <= float(val)

    elif ct == "arg_eq":
        arg, val = check["arg"], check["value"]
        actual = tool_args.get(arg)
        desc = f"arg {arg} == {val}"
        return desc, actual == val

    elif ct == "arg_absent":
        arg = check["arg"]
        desc = f"arg {arg} absent"
        return desc, not tool_args.get(arg)

    elif ct == "arg_present":
        arg = check["arg"]
        desc = f"arg {arg} present"
        return desc, bool(tool_args.get(arg))

    elif ct == "data_nonempty":
        desc = "data nonempty"
        if tool_data is None:
            return desc, False
        if isinstance(tool_data, (dict, list)):
            return desc, len(tool_data) > 0
        if isinstance(tool_data, str):
            return desc, len(tool_data.strip()) > 0
        return desc, True

    elif ct == "data_field_equals":
        field, val = check["field"], check["value"]
        desc = f"data.{field} == {val}"
        actual = _resolve_field(tool_data, field)
        if isinstance(val, str) and isinstance(actual, str):
            return desc, actual.lower() == val.lower()
        return desc, actual == val

    elif ct == "data_field_true":
        field = check["field"]
        desc = f"data.{field} is true"
        return desc, _resolve_field(tool_data, field) is True

    elif ct == "data_field_false":
        field = check["field"]
        desc = f"data.{field} is false"
        return desc, _resolve_field(tool_data, field) is False

    elif ct == "data_field_gte":
        field, val = check["field"], check["value"]
        desc = f"data.{field} >= {val}"
        actual = _resolve_field(tool_data, field)
        if actual is None:
            return desc, False
        return desc, float(actual) >= float(val)

    elif ct == "data_field_lte":
        field, val = check["field"], check["value"]
        desc = f"data.{field} <= {val}"
        actual = _resolve_field(tool_data, field)
        if actual is None:
            return desc, False
        return desc, float(actual) <= float(val)

    elif ct == "data_list_length_gte":
        field, val = check["field"], check["value"]
        desc = f"len(data.{field}) >= {val}"
        lst = _resolve_field(tool_data, field)
        if not isinstance(lst, list):
            return desc, False
        return desc, len(lst) >= val

    elif ct == "data_list_length_lte":
        field, val = check["field"], check["value"]
        desc = f"len(data.{field}) <= {val}"
        lst = _resolve_field(tool_data, field)
        if not isinstance(lst, list):
            return desc, False
        return desc, len(lst) <= val

    elif ct == "data_list_length_eq":
        field, val = check["field"], check["value"]
        desc = f"len(data.{field}) == {val}"
        lst = _resolve_field(tool_data, field)
        if not isinstance(lst, list):
            return desc, False
        return desc, len(lst) == val

    elif ct == "data_list_contains":
        field = check["field"]
        key, val = check["key"], check["value"]
        desc = f"data.{field} contains {key}={val}"
        lst = _resolve_field(tool_data, field)
        if not isinstance(lst, list):
            return desc, False
        return desc, any(
            (item.get(key, "").upper() if isinstance(item.get(key), str) else item.get(key)) ==
            (val.upper() if isinstance(val, str) else val)
            for item in lst if isinstance(item, dict)
        )

    elif ct == "data_contains_string":
        val = check["value"]
        desc = f"data contains '{val}'"
        return desc, val.lower() in str(tool_data).lower() if tool_data else False

    elif ct == "data_handles_error":
        desc = "handles error gracefully"
        if tool_data is None:
            return desc, True
        if isinstance(tool_data, dict):
            return desc, True
        return desc, True

    elif ct == "data_is_type":
        expected = check["value"]
        desc = f"data is {expected}"
        if expected == "dict":
            return desc, isinstance(tool_data, dict)
        elif expected == "list":
            return desc, isinstance(tool_data, list)
        elif expected == "string":
            return desc, isinstance(tool_data, str)
        return desc, True

    else:
        return f"unknown check type: {ct}", False


# ---------------------------------------------------------------------------
# LLM single-tool-call
# ---------------------------------------------------------------------------

def ask_for_tool_call(question: str, model: str, api_key: str, provider: str = "auto") -> dict:
    """Ask the LLM a question and get back its tool call choice."""
    provider = resolve_provider(model, provider)
    api_url = OPENAI_URL if provider == "openai" else OPENROUTER_URL
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\nAnswer the question using exactly ONE tool call. Do not chain multiple calls. Do not answer from prior knowledge. If one tool directly matches the request, call that exact tool rather than a broader adjacent tool. For exact symbol searches use grn_gene_search; for source-to-target routes use grn_pathfinding; for species capability questions use grn_species; for provenance and methods use grn_provenance; for screening requests use grn_dsrna_screen; for TF activity shifts use grn_diff_regulation; for inferred-edge questions use grn_inferred_edges; if the user explicitly says regulon, use grn_regulon even if the gene may be non-TF or have zero targets; for multi-gene upstream-regulator ranking use grn_upstream and preserve an explicit species such as human."},
        {"role": "user", "content": question},
    ]

    try:
        payload_obj = {
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
        }
        if provider == "openai":
            payload_obj["max_completion_tokens"] = 1024
        else:
            payload_obj["max_tokens"] = 1024
        payload = json.dumps(payload_obj).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        data = None
        last_err = None
        for attempt in range(API_RETRIES):
            try:
                with urllib.request.urlopen(req, timeout=API_TIMEOUT_S) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                last_err = f"HTTP Error {e.code}: {body[:300]}"
                if (
                    e.code == 429
                    or "rate limit" in body.lower()
                    or "too many requests" in body.lower()
                    or "upstream idle timeout exceeded" in body.lower()
                    or "timed out" in body.lower()
                ):
                    time.sleep(min(API_BACKOFF_S * (2 ** attempt), 60))
                    continue
                raise
            except Exception as e:
                last_err = str(e)
                if (
                    "429" in last_err
                    or "rate limit" in last_err.lower()
                    or "too many requests" in last_err.lower()
                    or "upstream idle timeout exceeded" in last_err.lower()
                    or "timed out" in last_err.lower()
                ):
                    time.sleep(min(API_BACKOFF_S * (2 ** attempt), 60))
                    continue
                raise
        if data is None:
            return {"error": last_err or "api request failed", "name": None, "args": {}}

        if "choices" not in data:
            err = data.get("error", {})
            if isinstance(err, dict):
                err = err.get("message", str(data))
            if isinstance(err, str) and ("rate limit" in err.lower() or "too many requests" in err.lower()):
                return {"error": f"rate_limited: {err}", "name": None, "args": {}}
            return {"error": str(err), "name": None, "args": {}}

        msg = data["choices"][0]["message"]
        if msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            fn = tc["function"]
            try:
                args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
            except json.JSONDecodeError:
                args = {}
            return {"name": fn["name"], "args": args, "error": None}
        else:
            return {"name": None, "args": {}, "error": "no_tool_call", "content": msg.get("content", "")}

    except Exception as e:
        return {"name": None, "args": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Single-skill LLM test harness")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider", default="auto", choices=["auto", "openrouter", "openai"])
    parser.add_argument("--http", default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--skill", default=None, help="Run only tests for this skill")
    parser.add_argument("--limit", type=int, default=None, help="Run only first N tests")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls (seconds)")
    parser.add_argument("--resume", default=None, help="Resume from partial results file")
    parser.add_argument("--cases", default=str(SKILLS_DIR / "_test_llm_cases.json"),
                        help="Test cases JSON file")
    args = parser.parse_args()

    provider = resolve_provider(args.model, args.provider)
    api_key = get_api_key(provider)
    if not api_key:
        env_name = "OPENAI_API_KEY" if provider == "openai" else "OPENROUTER_API_KEY"
        print(f"ERROR: Set {env_name} environment variable", file=sys.stderr)
        sys.exit(1)

    # Load test cases
    with open(args.cases) as f:
        all_cases = json.load(f)

    cases = all_cases
    if args.skill:
        cases = [c for c in cases if c["skill"] == args.skill]
    if args.limit:
        cases = cases[:args.limit]

    # Resume support
    completed = {}
    if args.resume and os.path.exists(args.resume):
        with open(args.resume) as f:
            prev = json.load(f)
        for r in prev.get("results", []):
            if r.get("grade") == "PASS":
                completed[r["label"]] = r
        print(f"Resuming: {len(completed)} passed tests kept, retrying failures")

    skills_in_test = sorted(set(c["skill"] for c in cases))
    print(f"Model: {args.model}")
    print(f"Tests: {len(cases)} ({len(skills_in_test)} skills)")
    print(f"Delay: {args.delay}s between calls")
    print()

    all_results = []
    for i, tc in enumerate(cases):
        if tc["label"] in completed:
            all_results.append(completed[tc["label"]])
            continue

        print(f"[{i+1}/{len(cases)}] {tc['skill']}: {tc['label']}")

        if i > 0 and tc["label"] not in completed:
            time.sleep(args.delay)

        t0 = time.time()
        response = ask_for_tool_call(tc["question"], args.model, api_key, provider=provider)
        api_time = time.time() - t0

        tool_name = response.get("name")
        tool_args = response.get("args", {})

        # Execute the tool if we got a call
        tool_data = None
        if tool_name and not response.get("error"):
            try:
                raw = execute_tool(tool_name, tool_args, args.http)
                clean = raw.strip()
                if clean.endswith("... [truncated]"):
                    clean = clean.rsplit("\n", 1)[0]
                tool_data = json.loads(clean)
            except json.JSONDecodeError:
                tool_data = _execute_full(tool_name, tool_args, args.http)
            except Exception:
                tool_data = None

        # Grade using check descriptors
        check_results = []
        for check in tc.get("checks", []):
            try:
                desc, passed = evaluate_check(check, tool_name, tool_args, tool_data)
            except Exception as e:
                desc = f"{check.get('type', '?')} [exception: {e}]"
                passed = False
            check_results.append({"check": desc, "pass": passed})

        grade = "PASS" if check_results and all(c["pass"] for c in check_results) else "FAIL"

        expected_tools = tc.get("expected_tools", [])
        tool_correct = tool_name in expected_tools if expected_tools else True

        result = {
            "skill": tc["skill"],
            "label": tc["label"],
            "question": tc["question"],
            "expected_tools": expected_tools,
            "actual_tool": tool_name,
            "tool_args": tool_args,
            "tool_correct": tool_correct,
            "grade": grade,
            "checks": check_results,
            "api_time_s": round(api_time, 1),
            "error": response.get("error"),
            "error_category": classify_error(response.get("error")),
            "failure_mode": classify_failure_mode(tool_name, expected_tools, response.get("error"), grade),
        }
        all_results.append(result)

        status = "✓" if grade == "PASS" else "✗"
        tool_mark = "✓" if tool_correct else "✗"
        print(f"  {status} {grade}  tool:{tool_mark} {tool_name or 'NONE'}({json.dumps(tool_args)[:80]})  [{api_time:.1f}s]")
        if args.verbose or grade == "FAIL":
            for c in check_results:
                mark = "✓" if c["pass"] else "✗"
                print(f"    {mark} {c['check']}")

        # Save incrementally
        out_path = SKILLS_DIR / "_test_results_llm_single.json"
        with open(out_path, "w") as f:
            json.dump({"model": args.model, "results": all_results}, f, indent=2)

    # Summary
    print(f"\n{'=' * 70}")
    print("SINGLE-SKILL LLM TEST REPORT")
    print(f"{'=' * 70}")

    from collections import Counter
    skill_stats = {}
    tool_selection_correct = 0
    for r in all_results:
        s = r["skill"]
        if s not in skill_stats:
            skill_stats[s] = {"pass": 0, "fail": 0, "tool_correct": 0, "total": 0}
        skill_stats[s]["total"] += 1
        if r["grade"] == "PASS":
            skill_stats[s]["pass"] += 1
        else:
            skill_stats[s]["fail"] += 1
        if r.get("tool_correct", True):
            skill_stats[s]["tool_correct"] += 1
            tool_selection_correct += 1

    print("\n--- Per-Skill Summary ---")
    for s in sorted(skill_stats):
        st = skill_stats[s]
        icon = "✓" if st["fail"] == 0 else "✗"
        print(f"  {icon} {s}: {st['pass']}/{st['total']} pass, tool-select: {st['tool_correct']}/{st['total']}")

    passed = sum(r["grade"] == "PASS" for r in all_results)
    total = len(all_results)
    print(f"\n{'=' * 70}")
    print(f"TOTAL: {passed}/{total} PASS")
    print(f"Tool selection accuracy: {tool_selection_correct}/{total} ({100*tool_selection_correct/total:.1f}%)")
    print(f"{'=' * 70}")

    out_path = SKILLS_DIR / "_test_results_llm_single.json"
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
