---
name: grn-validation-plan
description: Use when the user wants an execution-ready follow-up plan for a gene list and intent: what to do next, in what order, with decision gates, blockers, and success criteria. Good for requests like 'build a validation plan', 'how should I follow this up', or 'what experiments should I run next'. Often follows grn-coverage-report and can be reduced with grn-minimal-validation.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-validation-plan/scripts/run.py --gene-ids TP53,BAX,MDM2 --intent experiment
backend/venv/bin/python .agents/skills/grn-validation-plan/scripts/run.py --gene-ids Peaxi162Scf00118g00310 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-validation-plan/scripts/run.py --gene-ids TP53,BAX --intent network --http http://localhost:8000
```

## Notes

- use this when the user wants a go/no-go style plan rather than only a descriptive brief
- output is structured for downstream rendering into a checklist or validation matrix
- if the user first asks whether the species is ready for the intent, run `grn-coverage-report` before this skill
- if the user also asks for the smallest defensible next step, follow this with `grn-minimal-validation`
