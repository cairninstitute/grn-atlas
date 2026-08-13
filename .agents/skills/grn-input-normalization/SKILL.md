---
name: grn-input-normalization
description: "Use when the researcher pastes messy input that should be cleaned up before atlas import or analysis: mixed separators, aliases, duplicated rows, CSV/TSV snippets, mixed-species lists, or partially malformed hit lists. Trigger on prompts like 'clean this up', 'normalize this pasted list', 'what can be mapped cleanly', 'separate the mixed-species rows', or 'prepare this DEG snippet for atlas analysis'. Prefer this over grn-dataset-import when the main need is deterministic preprocessing and normalization before downstream interpretation."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-input-normalization/scripts/run.py --content $'TP53\nbax\ntumor protein p53\nCDKN1A'
backend/venv/bin/python .agents/skills/grn-input-normalization/scripts/run.py --file /path/to/deg.csv --species human
```

### Parameters

- `--content` — inline pasted content
- `--file` — local file path instead of inline content
- `--species` — optional species filter for disambiguation
- `--filename` — optional source filename label
- `--http URL` — optional running GRN Atlas server

Exactly one of `--content` or `--file` is required.

## Routing boundary

- Use this skill when the main task is **cleaning or normalizing messy user input before analysis**
- Use `grn-dataset-import` when the user explicitly wants the atlas import report itself
- Use `grn-user-gene-set-analysis` when the user mainly wants a biological interpretation rather than preprocessing details

## Output

JSON object containing:

- input type and filename
- species guess and species distribution
- duplicate/ambiguous/unmapped summaries
- row-level normalized results
- mixed-species detection
- recommended next skill
- warnings and normalization summary

