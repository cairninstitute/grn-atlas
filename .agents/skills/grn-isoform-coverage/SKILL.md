---
name: grn-isoform-coverage
description: "Check which transcript isoforms of a gene are hit by a dsRNA and how many siRNA sites each isoform has. Use for isoform-aware RNAi design."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-isoform-coverage/scripts/run.py --target-gene <value> --species <value>
```

### Parameters
- `--target-gene` — Target gene ID
- `--species` — Species name
- `--sequence` — Optional dsRNA sequence
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-isoform-coverage/scripts/run.py --target-gene <value> --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
