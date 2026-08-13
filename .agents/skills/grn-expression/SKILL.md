---
name: grn-expression
description: "Use when the task is to retrieve a gene's expression profile across samples or tissues, including simple prompts like 'expression of PIF4 in Arabidopsis', 'show HY5 expression', or 'what is the TPM profile of TP53'. This is for expression values, not coexpression or differential comparisons."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-expression/scripts/run.py --gene-id Peaxi162Scf00003g00410
```

### Parameters
- `--gene-id` (required) — Ensembl or species-specific gene ID
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-expression/scripts/run.py --gene-id Peaxi162Scf00003g00410 --http http://localhost:8000
```

### Output
JSON object with gene expression profile: per-sample TPM values, species, symbol, and matrix metadata.
