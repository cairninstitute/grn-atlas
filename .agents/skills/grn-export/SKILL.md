---
name: grn-export
description: "Export regulatory edges with genomic coordinates, promoter windows, and motif binding sites. Returns detailed edge data for a gene set in JSON or TSV format, suitable for downstream analysis or integration with other tools. Use this when the user explicitly asks to export edges or coordinates, even for a single gene or a non-TF gene, rather than detouring into search."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-export/scripts/run.py --gene-ids AT1G01010,AT1G01020
backend/venv/bin/python .agents/skills/grn-export/scripts/run.py --gene-ids AT1G01010,AT1G01020 --format tsv
```

### Parameters
- `--gene-ids` (required) — comma-separated gene IDs
- `--format` (optional, default "json") — output format, choices: json, tsv
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-export/scripts/run.py --gene-ids AT1G01010,AT1G01020 --http http://localhost:8000
```

### Output
JSON object (or TSV text) with regulatory edges annotated with confidence, provenance, genomic coordinates, and promoter windows.
