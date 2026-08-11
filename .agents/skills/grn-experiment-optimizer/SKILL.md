---
name: grn-experiment-optimizer
description: "Use when the user wants a constraint-aware follow-up plan rather than a generic next-step list. Good for prompts like 'what should I do with a small budget', 'I only have one week', or 'rank experiments I can run with expression and in-silico assays only'. Builds on experiment prioritization but explicitly adjusts for feasibility constraints."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-experiment-optimizer/scripts/run.py --gene-ids TP53,BAX --budget-level low --timeline-days 3
backend/venv/bin/python .agents/skills/grn-experiment-optimizer/scripts/run.py --gene-ids AT1G49720 --species arabidopsis --allowed-assays expression,in_silico
```

### Parameters
- `--gene-ids` (required) — comma-separated atlas gene IDs
- `--intent` — experiment intent
- `--species` — optional species override
- `--budget-level` — `low`, `medium`, or `high`
- `--timeline-days` — approximate time constraint
- `--allowed-assays` — comma-separated assay classes such as `expression`, `in_silico`, `rnai`, `motif`, `comparative`, `trait`
- `--max-recommendations` — maximum ranked experiments to return
- `--http URL` — optional running GRN Atlas server

### Output

JSON object containing:
- ranked experiments with base and optimized scores
- cost and timeline tiers
- constraint notes explaining penalties/boosts
- excluded genes and warnings
