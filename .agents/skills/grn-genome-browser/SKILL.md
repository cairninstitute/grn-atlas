---
name: grn-genome-browser
description: "Query genome coordinates, chromosomal positions, and cross-species ortholog mappings. Supports genome-aware analyses and coordinate-based lookups."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-genome-browser/scripts/run.py --species <value> --gene-id <value>
```

### Parameters
- `--species` — Species name
- `--gene-id` — Gene ID for ortholog lookup
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-genome-browser/scripts/run.py --species <value> --gene-id <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
