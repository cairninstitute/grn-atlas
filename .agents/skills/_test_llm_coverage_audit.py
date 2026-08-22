#!/usr/bin/env python3
"""Static audit of LLM test coverage across skills and orchestration tools."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILLS_DIR))


def main() -> None:
    all_skills = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and p.name.startswith("grn-"))
    base_cases = json.loads((SKILLS_DIR / "_test_llm_cases.json").read_text())
    supplemental_case_paths = sorted(SKILLS_DIR.glob("_test_llm_cases_supplemental_*.json"))
    sup_cases = []
    for path in supplemental_case_paths:
        sup_cases.extend(json.loads(path.read_text()))
    single_skills = sorted(set(c["skill"].replace("_", "-") for c in base_cases + sup_cases))

    orch_text = (SKILLS_DIR / "_test_llm_orchestration.py").read_text()
    base_tool_names = sorted(set(n.replace("_", "-") for n in re.findall(r'"name": "(grn_[^"]+)"', orch_text)))
    import _test_llm_orchestration as orch
    tool_names = sorted(set(t["function"]["name"].replace("_", "-") for t in orch.TOOLS))
    extra_tool_names = sorted(set(tool_names) - set(base_tool_names))
    orchestration_paths = sorted(SKILLS_DIR.glob("_test_llm_orchestration_*.json"))
    orch_specs = []
    for path in orchestration_paths:
        orch_specs.extend(json.loads(path.read_text()))
    covered_in_chain = sorted(set(t.replace("_", "-") for q in orch_specs for t in q.get("covers_tools", [])))

    report = {
        "total_skills": len(all_skills),
        "single_skill_covered": len(single_skills),
        "single_skill_missing": [s for s in all_skills if s not in single_skills],
        "single_skill_case_inventory": len(base_cases) + len(sup_cases),
        "single_skill_baseline_cases": len(base_cases),
        "single_skill_supplemental_cases": len(sup_cases),
        "orchestration_tool_surface": len(tool_names),
        "orchestration_tool_missing_from_surface": [s for s in all_skills if s not in tool_names],
        "legacy_orchestration_tool_surface": len(base_tool_names),
        "supplemental_orchestration_tool_surface": len(extra_tool_names),
        "supplemental_orchestration_tools": extra_tool_names,
        "supplemental_chain_covered_tools": covered_in_chain,
        "supplemental_chain_missing_new_tools": [s for s in extra_tool_names if s not in covered_in_chain],
        "orchestration_question_inventory_files": [p.name for p in orchestration_paths],
        "single_skill_supplemental_files": [p.name for p in supplemental_case_paths],
    }
    out = SKILLS_DIR / "_test_llm_coverage_audit.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(out)


if __name__ == "__main__":
    main()
