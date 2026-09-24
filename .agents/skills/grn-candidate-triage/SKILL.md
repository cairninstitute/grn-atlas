---
name: grn-candidate-triage
description: Use to rank a candidate gene list for a specific intent and decide which genes deserve follow-up first. Good for requests like 'triage these candidates', 'rank TP53, BAX, and MDM2', or 'which genes should I prioritize'. Also use after literature-first phenotype ideation once candidate genes have been mapped into the atlas, especially for non-model workflows such as petunia pigment or trait targeting. Often followed by grn-hypothesis-compare, grn-experiment-prioritization, grn-coverage-report, or grn-research-brief.
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
- **always pass `--intent`** — it shifts scoring weights and is required for correct ranking:
  - `experiment` — lab validation, follow-up experiments, CRISPR/qPCR planning
  - `network` — topology analysis, regulator/target relationships, hub genes
  - `rnai` — RNAi/dsRNA knockdown candidate selection
  - `traits` — GWAS hits, phenotype associations, trait mapping
- if the user says "rank for experiments" or "prioritize for validation", use `--intent experiment`
- if the user says "RNAi candidates" or "knockdown targets", use `--intent rnai`
- for phenotype-first questions, it is often the ranking step after `grn-literature-review` or gene-set mapping
