---
name: grn-experiment-prioritization
description: Recommend the next analyses or experiments to run for one or more genes based on evidence support and species coverage, including perturbation, expression, motif, RNAi, and conservation follow-up.
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
