---
name: grn-orthology
description: "Use to find the corresponding ortholog gene in another species and inspect its local network. Good for requests like 'mouse ortholog of E2F1', 'does HY5 have a tomato ortholog', or 'orthologs of HY5 across species'. Not for judging whether a claim transfers across species; use grn-transferability for that, and grn-conservation for conserved edges."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-orthology/scripts/run.py --gene-id AT1G01010
```

### Parameters
- `--gene-id` (required) — Ensembl gene ID
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-orthology/scripts/run.py --gene-id AT1G01010 --http http://localhost:8000
```

### Output
JSON object with orthologous genes across species and their regulatory network connections.
