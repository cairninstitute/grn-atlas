---
name: grn-gene-info
description: "Use when a specific gene has already been identified and you need its detailed record: locus or Ensembl ID, symbol, species, aliases, type, or transcription-factor status. Often used immediately after grn-gene-search. Also use after grn-infer when the user asks to look up, inspect, or compare the shared TFs returned by a GRNBoost2 versus GENIE3 comparison. Not for finding unknown genes by keyword."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-gene-info/scripts/run.py --gene-id ENSG00000136997
backend/venv/bin/python .agents/skills/grn-gene-info/scripts/run.py --symbol MYC --species human
```

### Parameters
- `--gene-id` (optional) — Ensembl gene ID
- `--symbol` (optional) — gene symbol (requires --species)
- `--species` (optional) — species name, needed when using --symbol
- `--http URL` (optional) — base URL of a running GRN Atlas server

Must provide either --gene-id or --symbol.

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-gene-info/scripts/run.py --gene-id ENSG00000136997 --http http://localhost:8000
```

### Output
JSON object with gene metadata: id, symbol, name, species, gene_type, is_tf, synonyms.

## Notes

- use this after `grn-gene-search` when a user asks for a detailed record of a found gene
- use this after `grn-infer` when a user asks to look up shared, overlapping, or top predicted regulators by name
