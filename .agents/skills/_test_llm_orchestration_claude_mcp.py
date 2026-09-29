#!/usr/bin/env python3
"""
LLM orchestration test runner using claude CLI with MCP tool transport.

Instead of encoding tool docs in the system prompt and having the model
compose Bash commands, this runner configures the MCP server so Claude
calls grn_* tools natively.  This reduces per-question token cost.

Usage:
    backend/venv/bin/python .agents/skills/_test_llm_orchestration_claude_mcp.py
    backend/venv/bin/python .agents/skills/_test_llm_orchestration_claude_mcp.py --question 1
    backend/venv/bin/python .agents/skills/_test_llm_orchestration_claude_mcp.py --resume
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]

sys.path.insert(0, str(SKILLS_DIR))
import _test_llm_orchestration as orch

DEFAULT_MODEL = "claude-opus-4-6"
MAX_TIMEOUT_S = 600
MCP_PREFIX = "mcp__grn_atlas__"
MCP_CONFIG = REPO_ROOT / ".agents" / "mcp" / "mcp_config.json"

SYSTEM_PROMPT = orch.SYSTEM_PROMPT + """

IMPORTANT RULES:
- You MUST use grn_* tools to answer questions. Do not guess or answer from memory.
- If a tool is deferred, use ToolSearch to load it first, then call it.
- After gathering all needed data, provide a clear synthesized answer.
- For gene_ids parameters, always use comma-separated format (TP53,BAX,BCL2), never JSON arrays.
- For the types parameter on grn_network_patterns, use short codes: ffl, fbl, bi.
- For the action parameter on grn_perturbation, use short codes: ko, kd, oe.
"""


def _extract_tool_calls(stream_lines: list[str]) -> tuple[list[dict], str]:
    """Parse stream-json to extract MCP tool calls and final answer."""
    tool_calls = []
    final_answer = ""

    for line in stream_lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type")

        if etype == "assistant":
            msg = event.get("message", {})
            for block in msg.get("content", []):
                if block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name.startswith(MCP_PREFIX):
                        canonical = name[len(MCP_PREFIX):]
                        args = block.get("input", {})
                        tool_calls.append({"name": canonical, "args": args})

        if etype == "result":
            final_answer = event.get("result", "")

    return tool_calls, final_answer


def _build_allowed_tools() -> str:
    """Build allowedTools pattern for MCP tools + ToolSearch."""
    return "mcp__grn_atlas__*,ToolSearch"


def run_question(question: str, model: str, verbose: bool = False) -> dict:
    """Run a single question using claude CLI with MCP transport."""
    sp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    sp_file.write(SYSTEM_PROMPT)
    sp_file.close()

    cmd = [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--model", model,
        "--mcp-config", str(MCP_CONFIG),
        "--strict-mcp-config",
        "--allowedTools", _build_allowed_tools(),
        "--disallowedTools", "Bash,Agent,Edit,Write,Read,WebSearch,WebFetch,Skill",
        "--system-prompt-file", sp_file.name,
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
    tool_calls, final_answer = _extract_tool_calls(lines)

    if verbose:
        print(f"    Tool calls: {len(tool_calls)}")
        for tc in tool_calls:
            print(f"      → {tc['name']}({json.dumps(tc['args'])[:100]})")
        if final_answer:
            print(f"    Answer: {final_answer[:300]}")

    rounds = sum(1 for l in lines if '"type":"assistant"' in l or '"type": "assistant"' in l)

    error = None
    ans_lower = (final_answer or "").lower()
    if "session limit" in ans_lower or "hit your" in ans_lower:
        error = "session_limit"

    return {
        "tool_calls": tool_calls,
        "final_answer": final_answer,
        "rounds": max(rounds, 1),
        "error": error,
    }


def main():
    parser = argparse.ArgumentParser(description="LLM orchestration test via claude CLI + MCP")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--question", type=int, default=None, help="Run only question N (1-indexed)")
    parser.add_argument("--retries", type=int, default=1, help="Extra retries for non-pass")
    parser.add_argument("--resume", action="store_true", help="Resume from existing results file")
    parser.add_argument("--out", default=str(SKILLS_DIR / "_test_results_llm_orchestration_claude_mcp.json"))
    args = parser.parse_args()

    questions = orch.QUESTIONS
    if args.question is not None:
        idx = args.question - 1
        if idx < 0 or idx >= len(orch.QUESTIONS):
            print(f"ERROR: --question must be 1-{len(orch.QUESTIONS)}", file=sys.stderr)
            sys.exit(1)
        questions = [orch.QUESTIONS[idx]]

    out_path = Path(args.out)

    completed = {}
    if args.resume and out_path.exists():
        prev = json.loads(out_path.read_text())
        for r in prev:
            if r.get("grade") == "PASS":
                completed[r["question_id"]] = r
        print(f"Resuming: {len(completed)} passed questions kept")

    print(f"Model: {args.model} (via claude CLI + MCP)")
    print(f"Questions: {len(questions)}")
    print(f"Tools: {len(orch.TOOLS)} (via MCP server)")
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
        grade = "FAIL"
        for attempt in range(1, args.retries + 2):
            t0 = time.time()
            trace = run_question(q["question"], args.model, args.verbose)
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

            ans = (trace.get("final_answer") or "").lower()
            if "session limit" in ans or "hit your" in ans:
                session_limit_count += 1
                break

        final = attempts[-1].copy()
        final["attempts"] = attempts
        if grade == "PASS":
            pass_count += 1
        all_results.append(final)

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
