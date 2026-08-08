---
name: grn-experiment-prioritization
description: Use to recommend the next analyses or experiments for one or more candidate genes after triage. Good for requests like 'what should I test next', 'recommend follow-up experiments', or 'what analyses are highest value now'. Often follows grn-candidate-triage and feeds grn-research-brief.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-experiment-prioritization/scripts/run.py --gene-ids TP53 --intent experiment
backend/venv/bin/python .agents/skills/grn-experiment-prioritization/scripts/run.py --gene-ids Peaxi162Scf00118g00310 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-experiment-prioritization/scripts/run.py --gene-ids TP53,BAX --max-recommendations 3 --http http://localhost:8000
```

## Notes

- this is meant for “what should I do next?” style research questions
- it uses evidence and coverage context, so absent layers lower or suppress certain recommendations
