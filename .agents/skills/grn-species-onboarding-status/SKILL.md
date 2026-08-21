---
name: grn-species-onboarding-status
description: "Get onboarding readiness assessment for a species: gene count, edge count, TF annotation, transcriptome availability, ortholog coverage, and overall readiness score (0-1)."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-species-onboarding-status/scripts/run.py --species <value>
```

### Parameters
- `--species` — Species name to assess
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-species-onboarding-status/scripts/run.py --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
