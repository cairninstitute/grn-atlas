---
name: grn-crispr-compare
description: "Compare CRISPR editing strategies (knockout, CRISPRi, CRISPRa) for a target gene. Assesses suitability based on gene type, regulon size, and reversibility."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-crispr-compare/scripts/run.py --gene-id <value> --species <value>
```

### Parameters
- `--gene-id` — Target gene ID or symbol
- `--species` — Species
- `--modes` — Comma-separated modes: knockout,CRISPRi,CRISPRa
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-crispr-compare/scripts/run.py --gene-id <value> --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
