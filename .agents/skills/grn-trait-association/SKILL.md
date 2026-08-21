---
name: grn-trait-association
description: "Query GWAS trait associations for a gene or test trait enrichment in a gene list. Connects regulatory network genes to phenotypic outcomes."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-trait-association/scripts/run.py --gene-id <value> --gene-ids <value>
```

### Parameters
- `--gene-id` — Gene ID for trait lookup
- `--gene-ids` — Comma-separated gene IDs for trait enrichment
- `--species` — Species name
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-trait-association/scripts/run.py --gene-id <value> --gene-ids <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
