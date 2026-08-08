---
name: grn-minimal-validation
description: Use when the user wants the smallest defensible next step rather than a full plan: the minimal validation move, first experiment, prerequisite check, or stop/go gate. Good for requests like 'minimal next move', 'smallest validation step', or 'what is the quickest defensible follow-up'. Usually follows grn-validation-plan.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-minimal-validation/scripts/run.py --gene-ids TP53,BAX --intent experiment
backend/venv/bin/python .agents/skills/grn-minimal-validation/scripts/run.py --gene-ids Peaxi162Scf00118g00310 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-minimal-validation/scripts/run.py --gene-ids TP53,BAX --intent experiment --http http://localhost:8000
```

## Notes

- use this when the researcher wants the smallest defensible next action rather than the full validation matrix
- the output is intentionally compressed from `grn-validation-plan`, not a separate planning system
- when the user asks for coverage check -> full plan -> minimal next move, this is the final step in that sequence after `grn-validation-plan`
