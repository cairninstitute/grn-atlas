#!/usr/bin/env python3
"""
LLM orchestration test runner using the `claude` CLI as orchestrator.

Replaces the OpenRouter/OpenAI provider with `claude -p` (Claude Code print mode).
The claude CLI handles tool calling internally via Bash — we parse its stream-json
output to extract which GRN Atlas skills were called and grade accordingly.

Usage:
    backend/venv/bin/python .agents/skills/_test_llm_orchestration_claude_cli.py
    backend/venv/bin/python .agents/skills/_test_llm_orchestration_claude_cli.py --question 1
    backend/venv/bin/python .agents/skills/_test_llm_orchestration_claude_cli.py --model claude-opus-4-6
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
PYTHON = str(REPO_ROOT / "backend" / "venv" / "bin" / "python")

sys.path.insert(0, str(SKILLS_DIR))
import _test_llm_orchestration as orch

DEFAULT_MODEL = "claude-opus-4-6"
MAX_TIMEOUT_S = 600

# Build a mapping from skill directory name back to tool name.
# Explicit _TOOL_TO_SKILL entries take priority over default name mangling.
_SKILL_TO_TOOL = {}
for tdef in orch.TOOLS:
    fn_name = tdef["function"]["name"]
    skill_name = orch._TOOL_TO_SKILL.get(fn_name, fn_name.replace("_", "-"))
    if fn_name not in orch._TOOL_TO_SKILL:
        _SKILL_TO_TOOL.setdefault(skill_name, fn_name)
    else:
        _SKILL_TO_TOOL[skill_name] = fn_name


_ARG_MAP = {
    "query": "--query", "species": "--species", "limit": "--limit",
    "gene_id": "--gene-id", "symbol": "--symbol", "direction": "--direction",
    "min_confidence": "--min-confidence", "source": "--source", "target": "--target",
    "max_depth": "--max-depth", "gene_ids": "--gene-ids", "type": "--type",
    "top": "--top", "min_r": "--min-r", "action": "--action", "depth": "--depth",
    "species_b": "--species-b", "target_gene": "--target-gene",
    "interventions": "--interventions", "tf_a": "--tf-a", "tf_b": "--tf-b",
    "metric": "--metric", "sequence": "--sequence", "k": "--k",
    "types": "--types", "format": "--format",
    "tf_gene_id": "--tf-gene-id", "max_pvalue": "--max-pvalue",
    "min_score": "--min-score", "include_edge_support": "--include-edge-support",
    "algorithm": "--algorithm", "resolution": "--resolution",
    "top_modules": "--top-modules",
    "group_a": "--group-a", "group_b": "--group-b",
    "min_fold_change": "--min-fold-change",
    "min_importance": "--min-importance",
    "compare_curated": "--compare-curated",
    "scope": "--scope", "source_id": "--source-id", "target_id": "--target-id",
    "intent": "--intent", "target_species": "--target-species",
    "max_recommendations": "--max-recommendations",
    "max_candidates": "--max-candidates", "max_experiments": "--max-experiments",
    "content": "--content", "filename": "--filename",
    "top_terms": "--top-terms", "top_regulators": "--top-regulators",
    "top_candidates": "--top-candidates",
    "phenotype": "--phenotype",
    "min_abs_log2fc": "--min-abs-log2fc",
    "budget_level": "--budget-level", "timeline_days": "--timeline-days",
    "allowed_assays": "--allowed-assays",
    "years_back": "--years-back", "max_results": "--max-results",
    "top_n": "--top-n", "include_external": "--include-external",
    "position": "--position", "assembly": "--assembly", "window_type": "--window-type",
    "ref": "--ref", "alt": "--alt", "pam": "--pam",
    "product_min": "--product-min", "product_max": "--product-max",
    "combo_size": "--combo-size", "species_name": "--species-name",
    "intended_capabilities": "--intended-capabilities",
}


def _build_tool_docs() -> str:
    """Build a text description of all tools with their CLI invocation syntax."""
    lines = []
    for tdef in orch.TOOLS:
        fn = tdef["function"]
        name = fn["name"]
        desc = fn.get("description", "")
        skill_name = orch._TOOL_TO_SKILL.get(name, name.replace("_", "-"))
        script_path = f".agents/skills/{skill_name}/scripts/run.py"

        params = fn.get("parameters", {}).get("properties", {})
        required = fn.get("parameters", {}).get("required", [])

        arg_parts = []
        for pname, pspec in params.items():
            cli_flag = _ARG_MAP.get(pname, f"--{pname.replace('_', '-')}")
            pdesc = pspec.get("description", "")
            req = " (required)" if pname in required else ""
            arg_parts.append(f"    {cli_flag} <{pname}>{req} — {pdesc}")

        lines.append(f"### {name}")
        lines.append(f"Description: {desc}")
        lines.append(f"Command: backend/venv/bin/python {script_path}")
        if arg_parts:
            lines.append("Arguments:")
            lines.extend(arg_parts)
        lines.append("")

    return "\n".join(lines)


def _build_system_prompt() -> str:
    """Build system prompt for the claude CLI agent."""
    tool_docs = _build_tool_docs()
    return f"""{orch.SYSTEM_PROMPT}

## Available Tools

You have access to the following GRN Atlas tools. Call each one using Bash with the exact command shown.
After running a tool, read its stdout output and use the results to continue your analysis.

IMPORTANT RULES:
- You MUST use these tools to answer questions. Do not guess or answer from memory alone.
- Call tools using Bash. Example: backend/venv/bin/python .agents/skills/grn-gene-search/scripts/run.py --query TP53 --species human
- If a question requires multiple steps, call multiple tools sequentially.
- After gathering all needed data, provide a clear synthesized answer.
- Always pass --http http://localhost:8000 as the first argument to each tool if the backend server is running.

{tool_docs}"""


def _extract_tool_calls_from_stream(stream_lines: list[str]) -> tuple[list[dict], str]:
    """Parse stream-json lines to extract tool calls (Bash commands that invoke skills) and final answer."""
    tool_calls = []
    final_answer = ""

    # Pattern to match skill invocations in Bash commands
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

        etype = event.get("type")

        # Extract Bash tool calls
        if etype == "assistant":
            msg = event.get("message", {})
            content = msg.get("content", [])
            for block in content:
                if block.get("type") == "tool_use" and block.get("name") == "Bash":
                    cmd = block.get("input", {}).get("command", "")
                    m = skill_pattern.search(cmd)
                    if m:
                        skill_dir = m.group(1)
                        tool_name = _SKILL_TO_TOOL.get(skill_dir, skill_dir.replace("-", "_"))
                        args_str = m.group(2).strip()
                        args = _parse_cli_args(args_str)
                        tool_calls.append({"name": tool_name, "args": args})

        # Extract final result
        if etype == "result":
            final_answer = event.get("result", "")

    return tool_calls, final_answer


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


def run_question_claude(question: str, model: str, verbose: bool = False) -> dict:
    """Run a single question using claude CLI as orchestrator."""
    system_prompt = _build_system_prompt()

    # Write system prompt to a temp file to avoid shell argument length limits
    import tempfile
    sp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    sp_file.write(system_prompt)
    sp_file.close()

    cmd = [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--model", model,
        "--allowedTools", "Bash,Read",
        "--system-prompt-file", sp_file.name,
        "--strict-mcp-config",
        "--disallowedTools", "Agent,Edit,Write,WebSearch,WebFetch,Skill",
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
        return {
            "tool_calls": [],
            "final_answer": "[TIMEOUT]",
            "rounds": 0,
            "error": "timeout",
        }

    finally:
        os.unlink(sp_file.name)

    if proc.returncode != 0 and not proc.stdout:
        return {
            "tool_calls": [],
            "final_answer": f"[CLI ERROR: {proc.stderr[:500]}]",
            "rounds": 0,
            "error": proc.stderr[:500],
        }

    lines = proc.stdout.strip().split("\n")
    tool_calls, final_answer = _extract_tool_calls_from_stream(lines)

    if verbose:
        print(f"    Tool calls: {len(tool_calls)}")
        for tc in tool_calls:
            print(f"      → {tc['name']}({json.dumps(tc['args'])[:100]})")
        if final_answer:
            print(f"    Answer: {final_answer[:300]}")

    # Count rounds from assistant messages
    rounds = sum(1 for l in lines if '"type":"assistant"' in l or '"type": "assistant"' in l)

    return {
        "tool_calls": tool_calls,
        "final_answer": final_answer,
        "rounds": max(rounds, 1),
        "error": None,
    }


def main():
    parser = argparse.ArgumentParser(description="LLM orchestration test via claude CLI")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--question", type=int, default=None, help="Run only question N (1-indexed)")
    parser.add_argument("--retries", type=int, default=1, help="Extra retries for non-pass")
    parser.add_argument("--resume", action="store_true", help="Resume from existing results file")
    parser.add_argument("--out", default=str(SKILLS_DIR / "_test_results_llm_orchestration_claude.json"))
    args = parser.parse_args()

    questions = orch.QUESTIONS
    if args.question is not None:
        idx = args.question - 1
        if idx < 0 or idx >= len(orch.QUESTIONS):
            print(f"ERROR: --question must be 1-{len(orch.QUESTIONS)}", file=sys.stderr)
            sys.exit(1)
        questions = [orch.QUESTIONS[idx]]

    out_path = Path(args.out)

    # Resume: load previous results and skip passed questions
    completed = {}
    if args.resume and out_path.exists():
        prev = json.loads(out_path.read_text())
        for r in prev:
            if r.get("grade") == "PASS":
                completed[r["question_id"]] = r
        print(f"Resuming: {len(completed)} passed questions kept")

    print(f"Model: {args.model} (via claude CLI)")
    print(f"Questions: {len(questions)}")
    print(f"Tools: {len(orch.TOOLS)}")
    print()

    all_results = []
    pass_count = 0
    session_limit_count = 0

    for i, q in enumerate(questions):
        q_num = args.question or (i + 1)

        if q_num in completed:
            all_results.append(completed[q_num])
            pass_count += 1
            continue

        if session_limit_count >= 3:
            print(f"Q{q_num}: SKIPPED (session limit hit)", flush=True)
            all_results.append({
                "question_id": q_num, "question": q["question"],
                "grade": "SKIP", "checks": [], "tool_calls_count": 0,
                "unique_skills": 0, "tool_calls": [], "final_answer": "[SESSION LIMIT]",
                "rounds": 0, "elapsed_s": 0, "error": "session_limit", "attempts": [],
            })
            continue

        print(f"Q{q_num}/{len(orch.QUESTIONS)}: {q['question'][:80]}...", flush=True)

        attempts = []
        for attempt in range(1, args.retries + 2):
            t0 = time.time()
            trace = run_question_claude(q["question"], args.model, args.verbose)
            elapsed = time.time() - t0

            check_results = []
            for desc, pred in q["checks"]:
                try:
                    passed = pred(trace)
                except Exception as e:
                    passed = False
                    desc += f" [exception: {e}]"
                check_results.append({"check": desc, "pass": passed})

            grade = "PASS" if all(c["pass"] for c in check_results) else "FAIL"
            result = {
                "question_id": q_num,
                "question": q["question"],
                "grade": grade,
                "checks": check_results,
                "tool_calls_count": len(trace["tool_calls"]),
                "unique_skills": len(set(c["name"] for c in trace["tool_calls"])),
                "tool_calls": trace["tool_calls"],
                "final_answer": (trace.get("final_answer") or "")[:2000],
                "rounds": trace["rounds"],
                "elapsed_s": round(elapsed, 1),
                "error": trace["error"],
                "attempt": attempt,
            }
            attempts.append(result)

            status = "✓" if grade == "PASS" else "✗"
            print(f"  {status} {grade} attempt {attempt} ({len(trace['tool_calls'])} calls, "
                  f"{result['unique_skills']} skills, {elapsed:.1f}s)")
            for c in check_results:
                mark = "✓" if c["pass"] else "✗"
                print(f"    {mark} {c['check']}")
            print(flush=True)

            if grade == "PASS":
                break

            # Detect session limit
            ans = (trace.get("final_answer") or "").lower()
            if "session limit" in ans or "hit your" in ans:
                session_limit_count += 1
                break

        final = attempts[-1].copy()
        final["attempts"] = attempts
        if grade == "PASS":
            pass_count += 1
        all_results.append(final)

        # Save incrementally
        out_path.write_text(json.dumps(all_results, indent=2))

    total = len(all_results)
    print(f"{'=' * 60}")
    print(f"Results: {pass_count}/{total} PASS")
    print(f"Total tool calls: {sum(r['tool_calls_count'] for r in all_results)}")
    if total:
        print(f"Avg skills/question: {sum(r['unique_skills'] for r in all_results) / total:.1f}")

    out_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
