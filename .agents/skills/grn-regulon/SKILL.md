---
name: grn-regulon
description: "Extract the full regulon of a transcription factor: all direct and indirect targets at configurable depth. Use to get the complete set of genes regulated by a TF, for downstream enrichment or comparison. Prefer this over grn-network when the user explicitly asks for a regulon, even if the regulon may be empty because the gene is not a transcription factor."
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

## Routing notes

- If the user explicitly says `regulon`, use this skill rather than `grn-network`.
- If the gene turns out not to be a transcription factor, still use this skill so the result can show an empty or unsupported regulon cleanly.
- Use `grn-network` instead only when the user asks for the immediate local neighborhood, regulators, or targets of one gene without asking for a regulon.
