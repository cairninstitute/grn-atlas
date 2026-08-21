---
name: grn-tf-activity
description: "Infer TF activity from gene-level statistics (log2FC, z-scores). Accepts a gene×value map and scores TFs by regulon behavior using ULM or weighted mean methods with signed edges."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-tf-activity/scripts/run.py --species <value> --method <value>
```

### Parameters
- `--species` — Species name
- `--method` — Scoring method: ulm or wmean (default ulm)
- `--top` — Number of top TFs to return (default 25)
- `--genes` — Comma-separated gene_id:value pairs
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-tf-activity/scripts/run.py --species <value> --method <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
