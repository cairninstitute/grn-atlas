---
name: grn-regulon
description: "Extract the full regulon of a transcription factor: all direct and indirect targets at configurable depth. Use to get the complete set of genes regulated by a TF, for downstream enrichment or comparison."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-regulon/scripts/run.py --gene-id TP53
backend/venv/bin/python .agents/skills/grn-regulon/scripts/run.py --gene-id TP53 --depth 3 --min-confidence 0.7
```

### Parameters
- `--gene-id` (required) — transcription factor gene ID
- `--depth` (optional, default 2) — regulon expansion depth (1=direct targets only)
- `--min-confidence` (optional, default 0.0) — minimum edge confidence
- `--no-include-inferred` — exclude inferred edges
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON object with regulon gene list grouped by level, summary stats (total genes, genes per level), and gene metadata.
