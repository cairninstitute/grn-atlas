---
name: grn-benchmark-status
description: "View the living validation dashboard: atlas summary statistics, BEELINE benchmark AUROC/AUPRC, per-species validation reports, and quality assessments."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-benchmark-status/scripts/run.py
```

### Parameters
- No arguments required
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-benchmark-status/scripts/run.py --http http://localhost:8000
```

### Output
JSON object with analysis results.
