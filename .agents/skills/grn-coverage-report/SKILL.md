---
name: grn-coverage-report
description: Report whether a species has the required and optional layers needed for a given analysis intent, with readiness score, missing layers, and recommended next skills.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-coverage-report/scripts/run.py --species arabidopsis --intent expression
backend/venv/bin/python .agents/skills/grn-coverage-report/scripts/run.py --species tomato --intent motif
backend/venv/bin/python .agents/skills/grn-coverage-report/scripts/run.py --species human --intent traits --http http://localhost:8000
```

## Notes

- `--intent` should match the user's question type
- readiness is higher when required layers are present; optional layers refine downstream interpretation
