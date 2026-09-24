#!/usr/bin/env python3
"""
Single-skill LLM test runner using the `claude` CLI as orchestrator.

For each test case, asks claude to pick exactly one tool, parses what
tool it called from stream-json output, executes the tool for grading
data, and grades against ground truth.

Usage:
    backend/venv/bin/python .agents/skills/_test_llm_single_claude_cli.py
    backend/venv/bin/python .agents/skills/_test_llm_single_claude_cli.py --skill grn-network --verbose
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
PYTHON = str(REPO_ROOT / "backend" / "venv" / "bin" / "python")

sys.path.insert(0, str(SKILLS_DIR))
import _test_llm_orchestration as orch
from _test_llm_single_skill import evaluate_check, _execute_full, classify_failure_mode

DEFAULT_MODEL = "claude-opus-4-6"
MAX_TIMEOUT_S = 180

# Import mappings from the orchestration CLI runner
from _test_llm_orchestration_claude_cli import _SKILL_TO_TOOL, _ARG_MAP


def _build_compact_tool_docs() -> str:
    """Build a compact tool reference — name, one-line description, and args only."""
    lines = []
    for tdef in orch.TOOLS:
        fn = tdef["function"]
        name = fn["name"]
        desc = fn.get("description", "").split(".")[0].strip()[:80]
        skill_name = orch._TOOL_TO_SKILL.get(name, name.replace("_", "-"))
        script = f".agents/skills/{skill_name}/scripts/run.py"

        params = fn.get("parameters", {}).get("properties", {})
        required = fn.get("parameters", {}).get("required", [])
        args = []
        for pname in params:
            cli_flag = _ARG_MAP.get(pname, f"--{pname.replace('_', '-')}")
            req = "*" if pname in required else ""
            args.append(f"{cli_flag}{req}")

        args_str = " ".join(args) if args else "(no args)"
        lines.append(f"- **{name}**: {desc} | `backend/venv/bin/python {script} {args_str}`")

    return "\n".join(lines)


SINGLE_SYSTEM_PROMPT = orch.SYSTEM_PROMPT + """

Answer the question using exactly ONE tool call via Bash. Do not chain multiple calls.
Do not answer from prior knowledge.

CRITICAL RULES:
- NEVER explore the codebase, read source files, or query the database directly. The tools handle all data access internally.
- NEVER use Read, grep, find, sqlite3, or any other exploration command. Only call the skill scripts listed below.
- If the question contains pasted data (CSV rows, tables, gene lists), pass it to the tool via the --content argument. Do not parse or analyze the data yourself.
- If a parameter looks like a placeholder (e.g. {dataset_id}), pass it literally as the argument value.
- Call the tool IMMEDIATELY. Do not deliberate about whether data exists — the tool will report errors if needed.
- For --gene-ids, ALWAYS use comma-separated format: --gene-ids TP53,BAX,BCL2. NEVER use JSON array format like '["TP53","BAX"]'.
- For --types, use short codes: ffl (not feed-forward), fbl (not feedback-loop), bi (not bidirectional).
- For --action on perturbation, use short codes: ko (not knockout), kd (not knockdown), oe (not overexpression).
- For --scope on literature review, use: phenotype (when starting from a trait/phenotype), gene (when starting from a specific gene).

## Available Tools

Call each tool using Bash with the exact command shown. Required args marked with *.

""" + _build_compact_tool_docs()


def _extract_first_tool_call(stream_lines: list[str]) -> dict:
    """Parse stream-json to extract the first skill invocation."""
    skill_pattern = re.compile(
        r'\.agents/skills/([a-z0-9-]+)/scripts/run\.py(.*)$'
    )

    for line in stream_lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "assistant":
            msg = event.get("message", {})
            for block in msg.get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "Bash":
                    cmd = block.get("input", {}).get("command", "")
                    m = skill_pattern.search(cmd)
                    if m:
                        skill_dir = m.group(1)
                        tool_name = _SKILL_TO_TOOL.get(skill_dir, skill_dir.replace("-", "_"))
                        args_str = m.group(2).strip()
                        args = _parse_cli_args(args_str)
                        return {"name": tool_name, "args": args, "error": None}

    return {"name": None, "args": {}, "error": "no_tool_call"}


def _parse_cli_args(args_str: str) -> dict:
    """Parse CLI argument string into a dict."""
    import shlex
    args = {}
    try:
        parts = shlex.split(args_str)
    except ValueError:
        parts = args_str.split()
    i = 0
    while i < len(parts):
        if parts[i].startswith("--"):
            key = parts[i][2:].replace("-", "_")
            if key == "http":
                i += 2
                continue
            if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                args[key] = parts[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1
    return args


def ask_for_tool_call_claude(question: str, model: str) -> dict:
    """Ask claude CLI to pick a single tool for the question."""
    sp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    sp_file.write(SINGLE_SYSTEM_PROMPT)
    sp_file.close()

    cmd = [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--model", model,
        "--allowedTools", "Bash",
        "--system-prompt-file", sp_file.name,
        "--strict-mcp-config",
        "--disallowedTools", "Agent,Edit,Write,WebSearch,WebFetch,Skill,Read",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=question,
            timeout=MAX_TIMEOUT_S,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"name": None, "args": {}, "error": "timeout"}
    finally:
        os.unlink(sp_file.name)

    if proc.returncode != 0 and not proc.stdout:
        return {"name": None, "args": {}, "error": proc.stderr[:300]}

    lines = proc.stdout.strip().split("\n")
    result = _extract_first_tool_call(lines)

    # Check for session limit in the final result
    for line in lines:
        try:
            event = json.loads(line.strip())
            if event.get("type") == "result":
                text = (event.get("result") or "").lower()
                if "session limit" in text or "hit your" in text:
                    result["error"] = "session_limit"
        except (json.JSONDecodeError, TypeError):
            pass

    return result


def main():
    parser = argparse.ArgumentParser(description="Single-skill LLM test via claude CLI")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--skill", default=None, help="Run only tests for this skill")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", default=None, nargs="?", const="AUTO",
                        help="Resume from partial results (default: use --out file)")
    parser.add_argument("--out", default=str(SKILLS_DIR / "_test_results_llm_single_claude.json"))
    args = parser.parse_args()

    # Load all case files
    all_cases = []
    for cf in [
        SKILLS_DIR / "_test_llm_cases.json",
        SKILLS_DIR / "_test_llm_cases_supplemental_2026-08-21.json",
        SKILLS_DIR / "_test_llm_cases_supplemental_2026-08-22.json",
    ]:
        if cf.exists():
            with open(cf) as f:
                all_cases.extend(json.load(f))

    cases = all_cases
    if args.skill:
        cases = [c for c in cases if c["skill"] == args.skill]
    if args.limit:
        cases = cases[:args.limit]

    # Resume support
    completed = {}
    resume_file = args.resume
    if resume_file == "AUTO":
        resume_file = args.out
    if resume_file and os.path.exists(resume_file):
        with open(resume_file) as f:
            prev = json.load(f)
        for r in prev.get("results", []):
            if r.get("grade") in ("PASS", "FAIL") and r.get("error") != "session_limit":
                completed[r["label"]] = r
        n_pass = sum(1 for r in completed.values() if r["grade"] == "PASS")
        n_fail = sum(1 for r in completed.values() if r["grade"] == "FAIL")
        print(f"Resuming: {n_pass} PASS + {n_fail} FAIL kept, skipping all")

    skills_in_test = sorted(set(c["skill"] for c in cases))
    print(f"Model: {args.model} (via claude CLI)")
    print(f"Tests: {len(cases)} ({len(skills_in_test)} skills)")
    print()

    all_results = []
    pass_count = 0
    session_limit_count = 0
    out_path = Path(args.out)

    for i, tc in enumerate(cases):
        if tc["label"] in completed:
            all_results.append(completed[tc["label"]])
            if completed[tc["label"]].get("grade") == "PASS":
                pass_count += 1
            continue

        if session_limit_count >= 3:
            all_results.append({
                "skill": tc["skill"], "label": tc["label"], "question": tc["question"],
                "expected_tools": tc.get("expected_tools", []),
                "actual_tool": None, "tool_correct": False, "tool_args": {},
                "grade": "SKIP", "checks": [], "elapsed_s": 0, "error": "session_limit",
            })
            continue

        print(f"[{i+1}/{len(cases)}] {tc['skill']}: {tc['label']}", flush=True)

        t0 = time.time()
        response = ask_for_tool_call_claude(tc["question"], args.model)
        api_time = time.time() - t0

        if response.get("error") == "session_limit":
            session_limit_count += 1
            print(f"  SESSION LIMIT HIT ({session_limit_count}/3)", flush=True)

        tool_name = response.get("name")
        tool_args = response.get("args", {})

        # Execute the tool for grading data
        tool_data = None
        if tool_name and not response.get("error"):
            try:
                raw = orch.execute_tool(tool_name, tool_args, None)
                clean = raw.strip()
                if clean.endswith("... [truncated]"):
                    clean = clean.rsplit("\n", 1)[0]
                tool_data = json.loads(clean)
            except json.JSONDecodeError:
                tool_data = _execute_full(tool_name, tool_args, None)
            except Exception:
                tool_data = None

        # Grade
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
            "tool_correct": tool_correct,
            "tool_args": tool_args,
            "grade": grade,
            "checks": check_results,
            "elapsed_s": round(api_time, 1),
            "error": response.get("error"),
        }

        status = "✓ PASS" if grade == "PASS" else "✗ FAIL"
        tool_mark = "✓" if tool_correct else "✗"
        tool_display = f"{tool_name}({json.dumps(tool_args)[:80]})" if tool_name else "NONE({})"
        print(f"  {status} tool:{tool_mark} {tool_display} [{api_time:.1f}s]", flush=True)

        if args.verbose and grade == "FAIL":
            for c in check_results:
                mark = "✓" if c["pass"] else "✗"
                print(f"    {mark} {c['check']}")

        if grade == "PASS":
            pass_count += 1

        all_results.append(result)

        # Save incrementally
        summary = {
            "model": args.model,
            "provider": "claude-cli",
            "total": len(cases),
            "completed": len(all_results),
            "pass": pass_count,
            "results": all_results,
        }
        out_path.write_text(json.dumps(summary, indent=2))

    # Final save (covers completed/skipped cases added after last incremental save)
    summary = {
        "model": args.model,
        "provider": "claude-cli",
        "total": len(cases),
        "completed": len(all_results),
        "pass": pass_count,
        "results": all_results,
    }
    out_path.write_text(json.dumps(summary, indent=2))

    total = len(all_results)
    print(f"\n{'=' * 60}")
    print(f"Results: {pass_count}/{total} PASS ({pass_count/total*100:.1f}%)")

    # Per-skill breakdown
    skill_stats = {}
    for r in all_results:
        s = r["skill"]
        if s not in skill_stats:
            skill_stats[s] = {"pass": 0, "total": 0}
        skill_stats[s]["total"] += 1
        if r["grade"] == "PASS":
            skill_stats[s]["pass"] += 1

    print(f"\nPer-skill breakdown:")
    for s in sorted(skill_stats):
        st = skill_stats[s]
        print(f"  {s}: {st['pass']}/{st['total']}")

    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
