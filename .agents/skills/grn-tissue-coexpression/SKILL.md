---
name: grn-tissue-coexpression
description: "View tissue-specific coexpression weights for regulatory edges. Shows which tissues support a TF-target interaction based on expression correlation. Use for tissue-context questions like 'is this edge active in petals?'"
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-tissue-coexpression/scripts/run.py --gene-id <value> --source-id <value>
```

### Parameters
- `--gene-id` — Gene ID to query tissue weights for
- `--source-id` — Source TF ID for specific edge
- `--target-id` — Target gene ID for specific edge
- `--species` — Species to list tissues for
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-tissue-coexpression/scripts/run.py --gene-id <value> --source-id <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
