---
name: grn-stats
description: "Get atlas-wide or per-species statistics from the GRN Atlas database. Returns gene counts, interaction counts, species list, and TF counts. Use for quick orientation about the database contents."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-stats/scripts/run.py
backend/venv/bin/python .agents/skills/grn-stats/scripts/run.py --species human
```

### Parameters
- `--species` (optional) — get stats for a specific species instead of global
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON object with gene counts, interaction counts, species list (global) or species-specific TF/interaction counts.
