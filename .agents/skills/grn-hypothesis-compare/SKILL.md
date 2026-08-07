---
name: grn-hypothesis-compare
description: Compare competing candidate genes for the same analysis intent and explain which hypothesis is currently best supported, why, and what evidence would overturn it.
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
