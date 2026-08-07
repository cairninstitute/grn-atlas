---
name: grn-validation-plan
description: Build an execution-ready validation plan from a gene list and analysis intent, including ranked validation tracks, decision gates, blockers, success criteria, and an ordered execution checklist.
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
