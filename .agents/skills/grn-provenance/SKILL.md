---
name: grn-provenance
description: "Get the data provenance manifest for the GRN Atlas database. Use for exact provenance, methods, versions, source freshness, and source lists such as 'what methods generated inferred edges', 'which sources are stale', 'show version info', or 'what data sources are included'. Prefer this over grn-atlas-overview whenever the question is about methods, source status, versioning, or provenance details."
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
