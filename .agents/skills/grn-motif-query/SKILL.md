---
name: grn-motif-query
description: "Query TF binding motif hits in gene promoter regions using JASPAR 2024 position weight matrices. Returns motif positions, scores, and strand information."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-motif-query/scripts/run.py --gene-id <value> --tf-id <value>
```

### Parameters
- `--gene-id` — Gene ID to query promoter motifs for
- `--tf-id` — Filter to a specific TF motif
- `--species` — Species name
- `--threshold` — Score threshold (default 0.8)
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-motif-query/scripts/run.py --gene-id <value> --tf-id <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
