---
name: grn-gene-search
description: "Search for genes by name, symbol, or keyword across species in the GRN Atlas regulatory network database. Use when looking up gene identifiers, finding genes by keyword, or resolving gene symbols to IDs for human, mouse, Arabidopsis, tomato, or petunia."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-gene-search/scripts/run.py --query "MYB"
```

### Parameters
- `--query` (required) — search term (gene name, symbol, or keyword)
- `--species` (optional) — filter by species (e.g. "human", "petunia")
- `--limit` (optional, default 20) — max number of results
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-gene-search/scripts/run.py --query "MYB" --http http://localhost:8000
```

### Output
JSON array of gene objects with fields: id, symbol, name, species, gene_type, is_tf, synonyms.
