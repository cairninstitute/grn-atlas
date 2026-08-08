---
name: grn-confidence-boundary
description: Use to state what the current atlas evidence supports, does not support, and leaves uncertain for a candidate set and intent. Good for requests like 'how far can I trust this', 'what is still ambiguous', or 'state the confidence boundary'. Often follows grn-evidence-audit.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-confidence-boundary/scripts/run.py --gene-ids TP53,BAX --intent experiment
backend/venv/bin/python .agents/skills/grn-confidence-boundary/scripts/run.py --gene-ids Peaxi162Scf00118g00310 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-confidence-boundary/scripts/run.py --gene-ids TP53,MDM2 --intent network --http http://localhost:8000
```

## Notes

- use this when the researcher needs explicit guardrails on what the atlas can and cannot justify
- the output is conservative by design and treats missing layers as uncertainty, not negative evidence
