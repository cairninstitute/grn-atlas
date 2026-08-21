---
name: grn-perturbation-import
description: "Import observed perturbation results (CRISPR screens, knockdown data) for calibrating atlas predictions against experimental evidence."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-perturbation-import/scripts/run.py --species <value> --type <value>
```

### Parameters
- `--species` — Species
- `--type` — Perturbation type: CRISPR_KO, RNAi, etc.
- `--file` — Path to observations TSV
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-perturbation-import/scripts/run.py --species <value> --type <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
