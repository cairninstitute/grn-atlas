---
name: grn-consensus-ranking
description: "Use when the researcher wants a single ranked view that combines multiple atlas evidence layers rather than relying on one score alone. Good for prompts like 'which candidate is strongest overall' or 'give me a consensus ranking across evidence types'."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-consensus-ranking/scripts/run.py --gene-ids TP53,BAX,MDM2 --intent experiment
backend/venv/bin/python .agents/skills/grn-consensus-ranking/scripts/run.py --gene-ids AT1G49720,AT5G11260 --species arabidopsis --include-external
```

### Output

Ranks candidates by a consensus score that combines triage priority, evidence layers, readiness, and optional external literature support/contradiction.
