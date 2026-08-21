---
name: grn-workflow
description: "Run a packaged end-to-end research workflow. Available: deg-to-regulators (DEG list → upstream TFs), target-to-perturbation (gene → RNAi/CRISPR strategy), import-to-activity (dataset → TF scoring)."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-workflow/scripts/run.py --workflow <value> --species <value>
```

### Parameters
- `--workflow` — Workflow type: deg-to-regulators, target-to-perturbation, import-to-activity
- `--species` — Species
- `--gene-ids` — Comma-separated gene IDs
- `--dataset-id` — Imported dataset ID
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-workflow/scripts/run.py --workflow <value> --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
