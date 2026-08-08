---
name: grn-research-brief
description: Use when the user wants a structured research brief for a gene list and intent, combining ranked candidates, follow-up experiments, readiness, evidence, risks, and next steps. Good for requests like 'make a brief', 'summarize this for follow-up', or 'prepare a structured research summary'. Often built after candidate triage and experiment prioritization.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-research-brief/scripts/run.py --gene-ids TP53,BAX,MDM2 --intent experiment
backend/venv/bin/python .agents/skills/grn-research-brief/scripts/run.py --gene-ids Peaxi162Scf00118g00310 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-research-brief/scripts/run.py --gene-ids TP53,BAX --intent network --http http://localhost:8000
```

## Notes

- use this when the user wants a concrete next-step plan rather than a single lookup
- the brief is intentionally structured so a downstream agent or UI can render it directly
