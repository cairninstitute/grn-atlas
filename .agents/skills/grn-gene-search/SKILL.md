---
name: grn-gene-search
description: "Use when the gene identifier must be searched by exact symbol, alias, partial name, or keyword. This includes simple prompts like 'find TP53 in human', 'search MYC limit 1', 'find HY5', 'search for AN2', or resolving symbols to atlas gene IDs across the species currently loaded into the atlas. Not for detailed metadata after the gene is identified; use grn-gene-info next."
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
