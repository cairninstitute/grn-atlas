---
name: grn-study-packet
description: Use when preparing a shareable collaborator handoff or analysis packet for a gene list and intent. Bundles the research brief, validation plan, provenance, citations, and handoff context into one package. Trigger on requests like 'study packet', 'handoff', 'shareable packet', 'collaborator package', or 'preserve this analysis'.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-study-packet/scripts/run.py --gene-ids TP53,BAX,MDM2 --intent experiment
backend/venv/bin/python .agents/skills/grn-study-packet/scripts/run.py --gene-ids Peaxi162Scf00118g00310 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-study-packet/scripts/run.py --gene-ids TP53,BAX --intent network --http http://localhost:8000
```

## Notes

- use this when the result needs to be handed to a collaborator or preserved as a self-contained packet
- includes provenance and citation context so downstream reporting can stay reproducible
