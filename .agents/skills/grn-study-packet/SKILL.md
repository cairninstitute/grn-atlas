---
name: grn-study-packet
description: Build a shareable study packet from a gene list and analysis intent, bundling the research brief, validation plan, collaborator handoff notes, and citation/provenance context.
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
