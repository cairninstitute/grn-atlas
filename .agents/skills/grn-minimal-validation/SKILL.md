---
name: grn-minimal-validation
description: Turn a candidate set and analysis intent into the smallest defensible validation path, including the first step, prerequisite checks, stop/go gates, blockers, and fallback path.
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
