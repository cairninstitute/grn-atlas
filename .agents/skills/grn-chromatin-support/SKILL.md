---
name: grn-chromatin-support
description: "View chromatin accessibility peaks, enhancer-gene links, motif hits in peaks, and cis-regulatory support for a gene's regulatory edges."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-chromatin-support/scripts/run.py --gene-id <value>
```

### Parameters
- `--gene-id` — Gene ID to query
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-chromatin-support/scripts/run.py --gene-id <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
