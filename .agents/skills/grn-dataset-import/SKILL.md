---
name: grn-dataset-import
description: "Use when the researcher explicitly needs import or mapping before analysis: map a raw gene list, CSV, TSV, DEG table, or messy symbol list onto atlas genes and report ambiguous or unmapped rows. Trigger on requests like 'import this hit list', 'map these symbols', 'which rows failed to map', or 'normalize this DEG table'. Do not use for downstream biological interpretation if the user is really asking what the atlas says about the genes after mapping; use grn-user-gene-set-analysis for that next step."
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

## Routing boundary

- Use this skill when the core task is **mapping / normalization / unresolved rows**
- Do **not** use this skill when the core task is **interpretation / ranking / enrichment / upstream analysis**
- If the user says "analyze this hit list" and does not care about the intermediate mapping report, prefer `grn-user-gene-set-analysis`

### Output

JSON object containing:
- guessed dataset type
- mapped genes and gene IDs
- ambiguous rows with candidate matches
- unmapped rows
- species guess
- warnings for anything unresolved
