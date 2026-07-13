---
name: grn-conservation
description: "Analyze conservation of regulatory edges between two species. For a set of genes, identifies which regulatory interactions are conserved versus species-specific across the ortholog network."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-conservation/scripts/run.py --gene-ids AT1G01010,AT1G01020 --species-b human
```

### Parameters
- `--gene-ids` (required) — comma-separated gene IDs (species A)
- `--species-b` (required) — species to compare against
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-conservation/scripts/run.py --gene-ids AT1G01010,AT1G01020 --species-b human --http http://localhost:8000
```

### Output
JSON object with regulatory edges and their conservation status (conserved vs. species-specific) between the two species.
