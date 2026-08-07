---
name: grn-candidate-triage
description: Rank a gene list for a research intent using evidence support, TF status, and species coverage so a researcher can decide which candidates merit follow-up first.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-candidate-triage/scripts/run.py --gene-ids TP53,BAX,MDM2 --intent network
backend/venv/bin/python .agents/skills/grn-candidate-triage/scripts/run.py --gene-ids Peaxi162Scf00118g00310,Peaxi162Scf00119g00942 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-candidate-triage/scripts/run.py --gene-ids TP53,BAX --intent experiment --http http://localhost:8000
```

## Notes

- use this before deeper follow-up when the user has several plausible genes
- `--intent` shifts the scoring weights toward network, traits, RNAi, or general experiment planning
