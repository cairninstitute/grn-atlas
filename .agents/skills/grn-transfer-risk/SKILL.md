---
name: grn-transfer-risk
description: "Assess orthology transfer risk for a gene across species. Reports ortholog confidence, edge conservation ratio, and risk level (low/medium/high)."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-transfer-risk/scripts/run.py --gene-id <value> --target-species <value>
```

### Parameters
- `--gene-id` — Gene ID or symbol
- `--target-species` — Target species for transfer
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-transfer-risk/scripts/run.py --gene-id <value> --target-species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
