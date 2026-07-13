---
name: grn-enrichment
description: "Run overrepresentation analysis on a set of genes. Supports GO term enrichment, Reactome pathway enrichment, GWAS trait enrichment, and transcription factor binding motif enrichment. Returns significant terms with p-values and FDR correction."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-enrichment/scripts/run.py --gene-ids "ENSG00000136997,ENSG00000141510" --type go
```

### Parameters
- `--gene-ids` (required for go/pathway/motif) — comma-separated list of Ensembl gene IDs
- `--gene-id` (optional) — single gene ID for trait lookup (returns all GWAS associations for that gene)
- `--type` (required) — enrichment type: go, pathway, trait, or motif
- `--species` (optional) — species filter
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-enrichment/scripts/run.py --gene-ids "ENSG00000136997,ENSG00000141510" --type go --http http://localhost:8000
```

### Output
JSON object with enriched terms, each including term name, p-value, FDR-corrected q-value, and matched genes.
