---
name: grn-regulon-enrichment
description: "Test which TF regulons are enriched in a gene list using hypergeometric test with BH FDR correction. The standard 'which TFs regulate my DEG list?' analysis (decoupleR/DoRothEA convention)."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-regulon-enrichment/scripts/run.py --gene-ids <value> --species <value>
```

### Parameters
- `--gene-ids` — Comma-separated gene IDs to test
- `--species` — Species name
- `--min-confidence` — Minimum edge confidence (default 0.4)
- `--top` — Number of top TFs (default 25)
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-regulon-enrichment/scripts/run.py --gene-ids <value> --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
