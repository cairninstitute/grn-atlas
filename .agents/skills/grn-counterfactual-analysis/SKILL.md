---
name: grn-counterfactual-analysis
description: "Use when the researcher asks 'why not this gene?' or wants to know what evidence would overturn the current winner. Good for prompts like 'what would change the ranking' or 'what is the smallest evidence shift that flips the lead?'."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-counterfactual-analysis/scripts/run.py --gene-ids TP53,BAX,MDM2 --intent experiment
```

### Output

Explains the current lead candidate, runner-up, and the smallest evidence changes likely to overturn the ranking.
