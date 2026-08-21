---
name: grn-pathway-activity
description: "Score pathway activity from gene-level statistics. Computes mean gene values per pathway with t-test significance."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-pathway-activity/scripts/run.py --species <value> --top <value>
```

### Parameters
- `--species` — Species name
- `--top` — Number of top pathways (default 25)
- `--genes` — Comma-separated gene_id:value pairs
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-pathway-activity/scripts/run.py --species <value> --top <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
