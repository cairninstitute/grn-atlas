---
name: grn-differential-expression
description: "Use when the user asks which genes change between two conditions, tissues, or groups, or when they provide a precomputed differential-expression table that should be mapped onto atlas genes. Good for prompts like 'what is up in root vs inflorescence' or 'analyze this DEG table'. Not for TF activity scoring specifically; use grn-diff-regulation for regulator-centric analysis."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-differential-expression/scripts/run.py --species arabidopsis --group-a root --group-b inflorescence
backend/venv/bin/python .agents/skills/grn-differential-expression/scripts/run.py --file /path/to/deg.csv --species human
```

### Parameters
- `--species` — required for atlas group-vs-group mode; optional when importing a DE table
- `--group-a` — comma-separated tissues/conditions for atlas mode
- `--group-b` — comma-separated tissues/conditions for atlas mode
- `--content` — inline DEG table content
- `--file` — local DEG table path
- `--filename` — optional source filename label
- `--top` — maximum rows to return
- `--min-abs-log2fc` — filter threshold for atlas mode
- `--http URL` — optional running GRN Atlas server

Provide either atlas groups (`--species`, `--group-a`, `--group-b`) or a DEG table (`--content` / `--file`).

### Output

JSON object containing:
- mode (`atlas_groups` or `imported_table`)
- ranked genes by absolute log2 fold-change
- tissue/group metadata or import metadata
- warnings
- recommended downstream skills
