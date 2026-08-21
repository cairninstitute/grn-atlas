---
name: grn-celltype-compare
description: "Compare TF regulatory activity between two cell types or clusters. Uses imported DEG contrast data to identify differentially active regulators."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-celltype-compare/scripts/run.py --dataset-id <value> --cluster-a <value>
```

### Parameters
- `--dataset-id` — Imported dataset ID
- `--cluster-a` — First cluster ID
- `--cluster-b` — Second cluster ID
- `--species` — Species
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-celltype-compare/scripts/run.py --dataset-id <value> --cluster-a <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
