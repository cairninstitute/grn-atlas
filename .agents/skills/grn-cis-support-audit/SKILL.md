---
name: grn-cis-support-audit
description: "Assess whether a TF→target regulatory edge is supported by promoter motif, chromatin peak, enhancer linkage, and prior regulatory evidence. Returns a confidence tier (strong/moderate/weak/minimal) and lists missing evidence layers."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-cis-support-audit/scripts/run.py --source-id <TF> --target-id <target> --http http://localhost:8000
```

### Parameters
- `--source-id` — TF gene ID
- `--target-id` — Target gene ID
- `--species` — Optional species filter
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with confidence_tier, n_supporting_layers, missing_layers, and per-layer evidence details.
