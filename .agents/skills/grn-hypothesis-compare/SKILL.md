---
name: grn-hypothesis-compare
description: Use when the task is to compare competing gene hypotheses for the same intent and explain which is currently best supported, why, and what evidence would change the winner. Good for requests like 'compare competing candidates' or 'which hypothesis is strongest'. Usually follows grn-candidate-triage rather than replacing it.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-hypothesis-compare/scripts/run.py --gene-ids TP53,MDM2,BAX --intent experiment
backend/venv/bin/python .agents/skills/grn-hypothesis-compare/scripts/run.py --gene-ids Peaxi162Scf00118g00310,Peaxi162Scf00450g00110 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-hypothesis-compare/scripts/run.py --gene-ids TP53,BAX --intent network --http http://localhost:8000
```

## Notes

- use this when the researcher needs to choose between competing candidates rather than inspect one in isolation
- the output emphasizes decisive evidence differences and explicit overturn conditions
