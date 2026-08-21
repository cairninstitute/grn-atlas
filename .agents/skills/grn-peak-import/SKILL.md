---
name: grn-peak-import
description: "Import chromatin peaks (ATAC-seq, ChIP-seq, DAP-seq) with optional peak-gene linkages. Supports BED-like format with peak type and gene annotations."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-peak-import/scripts/run.py --species <value> --peaks-file <value>
```

### Parameters
- `--species` — Species
- `--peaks-file` — Path to BED-like peaks file
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-peak-import/scripts/run.py --species <value> --peaks-file <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
