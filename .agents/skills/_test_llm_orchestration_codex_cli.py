#!/usr/bin/env python3
"""Run GRN Atlas orchestration benchmarks through ChatGPT-authenticated Codex."""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
sys.path.insert(0, str(SKILLS_DIR))

import _test_llm_orchestration as orch
import _test_llm_orchestration_claude_cli as cli

DEFAULT_MODEL = "gpt-5.6-sol"
MAX_TIMEOUT_S = 600
SKILL_PATTERN = re.compile(r"\.agents/skills/([a-z0-9-]+)/scripts/run\.py(.*)$")


def extract_trace(lines: list[str], mcp: bool) -> tuple[list[dict], str, str | None]:
    """Extract local skill commands from Codex JSONL command-execution events."""
    tool_calls = []
    messages = []
    errors = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "item.completed":
            continue
        item = event.get("item", {})
        if item.get("type") == "error":
            message = item.get("message", "")
            if not message.startswith(("Skill descriptions were shortened", "Under-development features enabled")):
                errors.append(message)
        if item.get("type") == "command_execution":
            match = SKILL_PATTERN.search(item.get("command", ""))
            if match:
                skill_dir = match.group(1)
                tool_name = cli._SKILL_TO_TOOL.get(skill_dir, skill_dir.replace("-", "_"))
                tool_calls.append({"name": tool_name, "args": cli._parse_cli_args(match.group(2).strip())})
        elif mcp and item.get("type") == "mcp_tool_call" and item.get("server") == "grn_atlas":
            tool_calls.append({"name": item.get("tool", ""), "args": item.get("arguments") or {}})
        elif item.get("type") == "agent_message":
            messages.append(item.get("text", ""))
    return tool_calls, messages[-1] if messages else "", errors[-1] if errors else None


def run_question(question: str, model: str, mcp: bool) -> dict:
    prompt = f"""{orch.SYSTEM_PROMPT}

You are running one orchestration benchmark question. Work in read-only mode:
- Use the grn_atlas MCP tools, rather than answering from memory or using shell commands.
- Do not repeat a tool call with identical arguments. If a specialized tool directly returns the requested result, synthesize it rather than re-querying it.
- Do not edit files or invoke the test harness itself.
- Finish with a concise, evidence-backed answer to this question.

Question: {question}
"""
    cmd = [
        "codex", "exec", "--ephemeral", "--json", "--sandbox", "read-only",
        "--model", model, "--cd", str(REPO_ROOT), prompt,
    ]
    if mcp:
        # Codex parses per-run MCP overrides only after the ``exec`` subcommand.
        cmd[2:2] = [
            "-c", f'mcp_servers.grn_atlas.command="{REPO_ROOT / "backend" / "venv" / "bin" / "python"}"',
            "-c", f'mcp_servers.grn_atlas.args=["{REPO_ROOT / ".agents" / "mcp" / "grn_atlas_mcp_server.py"}"]',
            "-c", 'mcp_servers.grn_atlas.env={GRN_MCP_HTTP="http://127.0.0.1:8001"}',
        ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=MAX_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"tool_calls": [], "final_answer": "[TIMEOUT]", "rounds": 0, "error": "timeout"}

    lines = (proc.stdout or "").splitlines()
    tool_calls, final_answer, error = extract_trace(lines, mcp)
    if proc.returncode != 0:
        error = error or (proc.stderr or proc.stdout or "Codex CLI failed")[:1000]
        if not final_answer:
            final_answer = f"[CODEX CLI ERROR: {error}]"
    return {
        "tool_calls": tool_calls,
        "final_answer": final_answer,
        "rounds": sum(1 for line in lines if '"type":"turn.started"' in line),
        "error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM orchestration test via ChatGPT-authenticated Codex CLI")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--question", type=int, default=None, help="Run only question N (1-indexed)")
    parser.add_argument("--questions", help="Run comma-separated question IDs")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--mcp", action="store_true", help="Expose tools through the local stdio MCP server")
    parser.add_argument("--resume", action="store_true", help="Keep prior passing cases from --out")
    parser.add_argument("--out", default=str(SKILLS_DIR / "_test_results_llm_orchestration_codex.json"))
    args = parser.parse_args()

    if args.question is not None and args.questions:
        parser.error("use either --question or --questions")
    if args.questions:
        try:
            question_ids = [int(value) for value in args.questions.split(",")]
        except ValueError:
            parser.error("--questions must be comma-separated integers")
    elif args.question is not None:
        question_ids = [args.question]
    else:
        question_ids = list(range(1, len(orch.QUESTIONS) + 1))
    if any(not 1 <= question_id <= len(orch.QUESTIONS) for question_id in question_ids):
        parser.error(f"question IDs must be 1-{len(orch.QUESTIONS)}")
    selected = [(question_id, orch.QUESTIONS[question_id - 1]) for question_id in question_ids]
    out_path = Path(args.out)
    completed = {}
    if args.resume and out_path.exists():
        for result in json.loads(out_path.read_text()):
            if result.get("grade") == "PASS":
                completed[result["question_id"]] = result
    results = []
    transport = "MCP" if args.mcp else "shell skills"
    print(f"Model: {args.model} (via ChatGPT subscription / Codex CLI, {transport})")
    if completed:
        print(f"Resuming: keeping {len(completed)} prior passes")

    for question_id, question in selected:
        if question_id in completed:
            results.append(completed[question_id])
            continue
        attempts = []
        for attempt in range(1, args.retries + 2):
            started = time.time()
            trace = run_question(question["question"], args.model, args.mcp)
            checks = [{"check": desc, "pass": bool(predicate(trace))} for desc, predicate in question["checks"]]
            result = {
                "question_id": question_id,
                "question": question["question"],
                "grade": "PASS" if all(check["pass"] for check in checks) else "FAIL",
                "checks": checks,
                "tool_calls_count": len(trace["tool_calls"]),
                "unique_skills": len({call["name"] for call in trace["tool_calls"]}),
                "tool_calls": trace["tool_calls"],
                "final_answer": trace["final_answer"][:2000],
                "rounds": trace["rounds"],
                "elapsed_s": round(time.time() - started, 1),
                "error": trace["error"],
                "attempt": attempt,
            }
            attempts.append(result)
            print(f"Q{question_id}: {result['grade']} attempt {attempt} ({result['tool_calls_count']} calls, {result['elapsed_s']}s)", flush=True)
            if result["grade"] == "PASS":
                break

        final = attempts[-1].copy()
        final["attempts"] = attempts
        results.append(final)
        out_path.write_text(json.dumps(results, indent=2))

    passed = sum(result["grade"] == "PASS" for result in results)
    print(f"Results: {passed}/{len(results)} PASS")
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
