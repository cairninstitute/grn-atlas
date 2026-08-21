---
name: grn-trajectory-drivers
description: "Identify TF drivers of cell state transitions using sequential DEG contrasts. Scores TFs by consistent regulatory direction across transitions."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-trajectory-drivers/scripts/run.py --dataset-id <value> --contrasts <value>
```

### Parameters
- `--dataset-id` — Imported dataset ID
- `--contrasts` — Comma-separated contrast IDs
- `--species` — Species
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-trajectory-drivers/scripts/run.py --dataset-id <value> --contrasts <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
