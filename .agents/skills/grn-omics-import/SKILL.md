---
name: grn-omics-import
description: "Import a gene expression matrix (bulk, pseudobulk, or scRNA-seq) with optional cluster definitions and DEG contrasts. Creates a dataset for use with cell-type and activity workflows."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-omics-import/scripts/run.py --name <value> --species <value>
```

### Parameters
- `--name` — Dataset name
- `--species` — Species
- `--data-type` — Data type: bulk, pseudobulk, scRNA
- `--matrix` — Path to TSV matrix file
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-omics-import/scripts/run.py --name <value> --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
