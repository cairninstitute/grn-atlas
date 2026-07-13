---
name: grn-coexpression
description: "Find genes co-expressed with a given gene based on Pearson correlation of log2 TPM expression profiles. Returns the top co-expressed partners with correlation coefficients. Useful for discovering functionally related genes."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-coexpression/scripts/run.py --gene-id Peaxi162Scf00003g00410
```

### Parameters
- `--gene-id` (required) — gene ID
- `--top` (optional, default 20) — number of top co-expressed partners to return
- `--min-r` (optional, default 0.5) — minimum absolute Pearson correlation
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-coexpression/scripts/run.py --gene-id Peaxi162Scf00003g00410 --http http://localhost:8000
```

### Output
JSON object with list of co-expressed genes, each with correlation coefficient, symbol, and whether it is a TF.
