---
name: grn-study-report
description: Use when the output should be a collaborator-facing narrative report rather than a bundled packet. Converts the study packet or brief into a structured report with summary, validation status, and citations. Good for requests like 'study report', 'collaborator report', or 'write this up for a collaborator'. Often paired with grn-study-packet.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-study-report/scripts/run.py --gene-ids TP53,BAX,MDM2 --intent experiment
backend/venv/bin/python .agents/skills/grn-study-report/scripts/run.py --gene-ids Peaxi162Scf00118g00310 --intent rnai --species petunia
backend/venv/bin/python .agents/skills/grn-study-report/scripts/run.py --gene-ids TP53,BAX --intent network --http http://localhost:8000
```

## Notes

- use this when the output needs to be read directly by a collaborator, PI, or project channel rather than consumed as raw JSON
- the report preserves the full study packet and adds a ready-to-share markdown narrative
