---
name: grn-citations
description: "Export BibTeX citations for all data sources integrated into the GRN Atlas. Use when writing papers, reports, or documentation that references atlas data and needs proper citations."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-citations/scripts/run.py
```

### Parameters
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-citations/scripts/run.py --http http://localhost:8000
```

### Output
BibTeX-formatted text with citation entries for every data source the atlas integrates (TRRUST, PlantRegMap, JASPAR, etc.).
