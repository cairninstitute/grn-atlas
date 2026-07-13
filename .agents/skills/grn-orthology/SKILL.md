---
name: grn-orthology
description: "Find cross-species orthologs of a gene and their regulatory networks. Returns orthologous genes in other species with their regulators and targets, enabling comparative regulatory analysis across human, mouse, Arabidopsis, tomato, and petunia."
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
