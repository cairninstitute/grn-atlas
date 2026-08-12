---
name: grn-research-brief
description: Use when the user explicitly wants a structured brief, collaborator handoff, or execution-oriented summary for a gene list and intent, combining ranked candidates, follow-up experiments, readiness, evidence, risks, and next steps. Trigger on requests like 'make a brief', 'prepare a structured summary', 'package this for follow-up', or 'build a handoff-ready report'. Do not use when the user is simply asking to analyze a hit list or interpret a gene set; prefer grn-user-gene-set-analysis for that earlier analysis step.
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
- if the user says "analyze this hit list" without asking for a brief or handoff artifact, prefer `grn-user-gene-set-analysis`
