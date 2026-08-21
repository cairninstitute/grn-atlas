---
name: grn-pathway-enrichment
description: "Test which pathways are overrepresented in a gene list using hypergeometric test. Complements GO enrichment (grn-enrichment) with pathway-level analysis."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-pathway-enrichment/scripts/run.py --gene-ids <value> --species <value>
```

### Parameters
- `--gene-ids` — Comma-separated gene IDs
- `--species` — Species name
- `--top` — Number of top pathways (default 20)
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-pathway-enrichment/scripts/run.py --gene-ids <value> --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
