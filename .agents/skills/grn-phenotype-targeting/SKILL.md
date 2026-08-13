---
name: grn-phenotype-targeting
description: Use when the researcher starts from a phenotype, trait, or design objective rather than a gene list, especially prompts like 'which genes should I target to change flower color in petunia', 'who are the best ABA regulators to perturb in Arabidopsis', or 'turn this phenotype idea into atlas-grounded candidates'. This skill bridges literature-first ideation to atlas-grounded candidate ranking, readiness, and next-step follow-up.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-phenotype-targeting/scripts/run.py --species petunia --phenotype "change flower color" --intent rnai
backend/venv/bin/python .agents/skills/grn-phenotype-targeting/scripts/run.py --species arabidopsis --phenotype "ABA signaling drought response" --intent experiment
```

## Notes

- use this when the question begins with an outcome, not a defined hit list
- this skill does literature cue generation, atlas grounding, candidate ranking, readiness checks, and next-step recommendation in one structured output
- for messy pasted content, use `grn-input-normalization` first
