---
name: grn-crispr-offtargets
description: "Scan the transcriptome for CRISPR guide off-targets with configurable mismatch tolerance. Reports gene hits, positions, and mismatch counts."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-crispr-offtargets/scripts/run.py --guide <value> --species <value>
```

### Parameters
- `--guide` — 20-nt guide sequence
- `--species` — Species name
- `--max-mismatches` — Maximum mismatches (default 3)
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-crispr-offtargets/scripts/run.py --guide <value> --species <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
