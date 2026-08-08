---
name: grn-coverage-report
description: Use first when you need to know whether a species has enough atlas support for an analysis intent such as RNAi, transfer, or network follow-up. Reports readiness, missing layers, and recommended next skills. Often followed by grn-validation-plan or grn-minimal-validation.
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
- if the user asks for a coverage check plus a follow-up plan, call this first, then `grn-validation-plan`
- if the user asks for the smallest next move after the plan, call `grn-minimal-validation` after `grn-validation-plan`
