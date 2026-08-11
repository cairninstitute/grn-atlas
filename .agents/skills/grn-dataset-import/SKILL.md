---
name: grn-dataset-import
description: "Use when the researcher provides a gene list, CSV, or TSV that needs to be mapped onto atlas genes before analysis. Good for prompts like 'analyze this hit list', 'map these gene symbols', or 'import this DEG table'. Not for the downstream interpretation itself; use grn-user-gene-set-analysis next."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-dataset-import/scripts/run.py --content $'TP53\nBAX\nMYC'
backend/venv/bin/python .agents/skills/grn-dataset-import/scripts/run.py --file /path/to/genes.tsv --species arabidopsis
```

### Parameters
- `--content` — inline gene list or tabular content
- `--file` — local file to import instead of inline content
- `--species` — optional species filter for disambiguation
- `--filename` — optional source filename label
- `--http URL` — optional running GRN Atlas server

Exactly one of `--content` or `--file` is required.

### Output

JSON object containing:
- guessed dataset type
- mapped genes and gene IDs
- ambiguous rows with candidate matches
- unmapped rows
- species guess
- warnings for anything unresolved
