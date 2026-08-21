---
name: grn-family-rescue
description: "Rescue regulatory edges for a gene with sparse direct data by aggregating evidence from orthologs across species. Novel targets get reduced confidence (ortholog × edge × 0.7)."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-family-rescue/scripts/run.py --gene-id <value>
```

### Parameters
- `--gene-id` — Gene ID or symbol
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-family-rescue/scripts/run.py --gene-id <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
