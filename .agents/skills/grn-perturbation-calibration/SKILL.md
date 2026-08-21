---
name: grn-perturbation-calibration
description: "Compare predicted downstream effects with observed perturbation data. Reports concordance rate, direction agreement, and prediction accuracy."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-perturbation-calibration/scripts/run.py --gene <value> --species <value>
```

### Parameters
- `--gene` — Perturbed gene ID or symbol
- `--species` — Species
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-perturbation-calibration/scripts/run.py --gene <value> --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
