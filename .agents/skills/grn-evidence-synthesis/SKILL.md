---
name: grn-evidence-synthesis
description: Use when the user wants a writing-ready evidence summary for a gene or candidate set, including support, caveats, PMIDs, and citation context. Good for requests like 'write up the evidence', 'paper-style summary', or 'evidence synthesis'. Often follows grn-evidence-audit and grn-confidence-boundary.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-evidence-synthesis/scripts/run.py --gene-ids TP53,BAX --intent experiment
backend/venv/bin/python .agents/skills/grn-evidence-synthesis/scripts/run.py --gene-ids Peaxi162Scf00118g00310 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-evidence-synthesis/scripts/run.py --gene-ids TP53,BAX --intent experiment --http http://localhost:8000
```

## Notes

- use this when the researcher wants a writing-ready evidence summary without pretending the atlas performed a full literature review
- the PMIDs and citations come only from data already stored in the atlas and its provenance manifest
