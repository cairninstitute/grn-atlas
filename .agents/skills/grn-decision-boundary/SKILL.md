---
name: grn-decision-boundary
description: Use when the researcher needs a single decision-ready summary of what the atlas supports, what remains unsupported or ambiguous, what evidence would overturn the current winner, and what smallest next step reduces uncertainty most. Good for prompts like 'how far can I trust this', 'what would change the current winner', or 'what is the minimal defensible next move for these candidates'.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-decision-boundary/scripts/run.py --gene-ids TP53,BAX,MDM2 --intent experiment --species human
backend/venv/bin/python .agents/skills/grn-decision-boundary/scripts/run.py --gene-ids AN2,JAF13,DFR --intent rnai --species petunia
```

## Notes

- use this instead of manually chaining confidence boundary, counterfactual analysis, and minimal validation when the user wants one decision summary
- accepts atlas IDs or resolvable symbols
