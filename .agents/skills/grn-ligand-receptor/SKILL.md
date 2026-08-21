---
name: grn-ligand-receptor
description: "Find potential ligand-receptor signaling pairs from the regulatory network — non-TF genes that regulate TFs, suggesting intercellular signaling relationships."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-ligand-receptor/scripts/run.py --species <value> --gene-ids <value>
```

### Parameters
- `--species` — Species
- `--gene-ids` — Optional comma-separated gene IDs to filter
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-ligand-receptor/scripts/run.py --species <value> --gene-ids <value> --http http://localhost:8000
```

### Output
JSON object with analysis results.
