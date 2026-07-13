---
name: grn-species
description: "List all species in the GRN Atlas with their available capabilities. Returns a per-species matrix showing which features (expression, motifs, traits, orthologs, genome coordinates) are available."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-species/scripts/run.py
```

### Parameters
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-species/scripts/run.py --http http://localhost:8000
```

### Output
JSON array of species objects with capability flags indicating which data layers are available for each species.
