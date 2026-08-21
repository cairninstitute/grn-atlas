---
name: grn-pseudotime-activity
description: "Score TF activity along a pseudotime-ordered gene expression gradient. Identifies TFs whose regulon members show coordinated changes."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-pseudotime-activity/scripts/run.py --dataset-id <value> --genes <value>
```

### Parameters
- `--dataset-id` — Imported dataset ID
- `--genes` — Comma-separated gene_id:value pairs
- `--species` — Species
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-pseudotime-activity/scripts/run.py --dataset-id <value> --genes <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
