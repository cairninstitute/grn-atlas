---
name: grn-species
description: "Use when the question is about which species are available or what capabilities each species supports, such as 'which species have expression data', 'does petunia have RNAi support', or 'show species capability fields'. Prefer this over grn-atlas-overview whenever the user wants the concrete species list or per-species capability details."
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
