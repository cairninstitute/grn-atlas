---
name: grn-provenance
description: "Get the data provenance manifest for the GRN Atlas database. Returns version information, methods, and data sources with DOIs and citations. Use to understand what data the atlas contains and how to cite it."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-provenance/scripts/run.py
```

### Parameters
- `--freshness` (optional) — show data freshness audit (loaded vs latest versions) instead of full manifest
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-provenance/scripts/run.py --http http://localhost:8000
```

### Output
JSON object with data provenance manifest including version, methods, data sources, DOIs, and citation information.
