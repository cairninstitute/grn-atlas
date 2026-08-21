---
name: grn-celltype-upstream
description: "Find upstream TF regulators for a gene set, constrained to TFs that are expressed in a specific cell type or cluster from an imported dataset."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-celltype-upstream/scripts/run.py --dataset-id <value> --cluster-id <value>
```

### Parameters
- `--dataset-id` — Imported dataset ID
- `--cluster-id` — Cluster ID
- `--gene-ids` — Comma-separated gene IDs
- `--species` — Species
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-celltype-upstream/scripts/run.py --dataset-id <value> --cluster-id <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
