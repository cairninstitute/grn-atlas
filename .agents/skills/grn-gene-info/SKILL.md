---
name: grn-gene-info
description: "Get detailed information about a specific gene by its Ensembl ID or symbol. Returns gene metadata including symbol, name, species, type, synonyms, and whether it is a transcription factor."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-gene-info/scripts/run.py --gene-id ENSG00000136997
backend/venv/bin/python .agents/skills/grn-gene-info/scripts/run.py --symbol MYC --species human
```

### Parameters
- `--gene-id` (optional) — Ensembl gene ID
- `--symbol` (optional) — gene symbol (requires --species)
- `--species` (optional) — species name, needed when using --symbol
- `--http URL` (optional) — base URL of a running GRN Atlas server

Must provide either --gene-id or --symbol.

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-gene-info/scripts/run.py --gene-id ENSG00000136997 --http http://localhost:8000
```

### Output
JSON object with gene metadata: id, symbol, name, species, gene_type, is_tf, synonyms.
