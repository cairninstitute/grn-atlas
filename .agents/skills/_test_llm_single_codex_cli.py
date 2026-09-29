#!/usr/bin/env python3
"""Run the single-skill matrix through ChatGPT-authenticated Codex MCP."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
sys.path.insert(0, str(SKILLS_DIR))

import _test_llm_orchestration_codex_cli as codex
import _test_llm_single_matrix as matrix
from _test_llm_single_skill import _execute_full, evaluate_check

DEFAULT_MODEL = "gpt-5.6-terra"
MAX_TIMEOUT_S = 600
TOOL_ALIASES = {
    # Shell fallback events use skill-directory names; grade them against the
    # canonical MCP names exposed by the orchestration inventory.
    "grn_module": "grn_modules",
    "grn_infer": "grn_inferred_edges",
}


def choose_tool(question: str, model: str) -> dict:
    """Ask Codex to make exactly one MCP tool call and capture its first call."""
    prompt = f"""{codex.orch.SYSTEM_PROMPT}

You are running one single-skill routing benchmark. Work in read-only mode.
- Use exactly one grn_atlas MCP tool call; do not use shell commands.
- Choose the most specialized tool for the question and provide the required arguments.
- Do not call a second tool, inspect files, or edit anything.
- After the tool returns, give a concise answer.

Question: {question}
"""
    cmd = [
        "codex", "exec", "--ephemeral", "--json", "--sandbox", "read-only",
        "--model", model, "--cd", str(REPO_ROOT), prompt,
    ]
    cmd[2:2] = [
        "-c", f'mcp_servers.grn_atlas.command="{REPO_ROOT / "backend" / "venv" / "bin" / "python"}"',
        "-c", f'mcp_servers.grn_atlas.args=["{REPO_ROOT / ".agents" / "mcp" / "grn_atlas_mcp_server.py"}"]',
        "-c", 'mcp_servers.grn_atlas.env={GRN_MCP_HTTP="http://127.0.0.1:8001"}',
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=MAX_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"name": None, "args": {}, "error": "timeout"}

    calls, _, error = codex.extract_trace((proc.stdout or "").splitlines(), mcp=True)
    if proc.returncode != 0:
        error = error or (proc.stderr or proc.stdout or "Codex CLI failed")[:1000]
    if not calls:
        return {"name": None, "args": {}, "error": error or "no_tool_call"}
    first = calls[0]
    return {
        "name": TOOL_ALIASES.get(first["name"], first["name"]),
        "args": first["args"],
        "error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-skill LLM test via ChatGPT-authenticated Codex")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--http", required=True, help="Backend URL for HTTP fixture setup and grading")
    parser.add_argument("--skill")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--out", default=str(SKILLS_DIR / "_test_results_llm_single_codex.json"))
    args = parser.parse_args()

    cases = matrix._load_cases("auto")
    if args.skill:
        cases = [case for case in cases if case["skill"] == args.skill]
    if args.limit is not None:
        cases = cases[:args.limit]

    out_path = Path(args.out)
    completed = {}
    if args.resume and out_path.exists():
        for result in json.loads(out_path.read_text()).get("results", []):
            if result.get("grade") == "PASS":
                completed[result["label"]] = result

    results = []
    print(f"Model: {args.model} (via ChatGPT subscription / Codex MCP)")
    print(f"Tests: {len(cases)}")
    for index, case in enumerate(cases, start=1):
        if case["label"] in completed:
            results.append(completed[case["label"]])
            continue
        prepared, prep_error = matrix._prepare_case(case, args.http)
        if prep_error:
            results.append({**case, "grade": "SKIP", "error": prep_error["error"]})
            continue

        attempts = []
        for attempt in range(1, args.retries + 2):
            started = time.time()
            response = choose_tool(prepared["question"], args.model)
            tool_name, tool_args = response["name"], response["args"]
            tool_data = _execute_full(tool_name, tool_args, args.http) if tool_name else None
            checks = []
            for check in prepared.get("checks", []):
                description, passed = evaluate_check(check, tool_name, tool_args, tool_data)
                checks.append({"check": description, "pass": passed})
            result = {
                "skill": prepared["skill"], "label": prepared["label"],
                "question": prepared["question"], "expected_tools": prepared.get("expected_tools", []),
                "actual_tool": tool_name, "tool_args": tool_args,
                "tool_correct": tool_name in prepared.get("expected_tools", []),
                "grade": "PASS" if checks and all(check["pass"] for check in checks) else "FAIL",
                "checks": checks, "elapsed_s": round(time.time() - started, 1),
                "error": response["error"], "attempt": attempt,
            }
            attempts.append(result)
            print(f"[{index}/{len(cases)}] {prepared['label']}: {result['grade']} ({result['elapsed_s']}s)", flush=True)
            if result["grade"] == "PASS":
                break
        final = attempts[-1].copy()
        final["attempts"] = attempts
        results.append(final)
        out_path.write_text(json.dumps({"model": args.model, "results": results}, indent=2))

    passed = sum(result.get("grade") == "PASS" for result in results)
    print(f"Results: {passed}/{len(results)} PASS")


if __name__ == "__main__":
    main()
