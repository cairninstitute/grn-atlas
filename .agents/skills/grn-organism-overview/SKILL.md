---
name: grn-organism-overview
description: "Get a comprehensive overview of a species in the atlas: gene counts, interaction counts, TF coverage, data sources, expression panel, and available capabilities."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-organism-overview/scripts/run.py --species <value>
```

### Parameters
- `--species` — Species name
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-organism-overview/scripts/run.py --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
