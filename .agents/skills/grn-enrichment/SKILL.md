---
name: grn-enrichment
description: "Use when you already have a gene set and need GO, pathway, trait, or motif enrichment. This includes exact prompts like 'GO enrichment for these genes', 'pathway enrichment', 'trait enrichment for TP53', 'GWAS traits for TP53', 'is TP53 associated with cancer in GWAS data', or 'motif enrichment for these Arabidopsis TFs'. Prefer this whenever the task is enrichment analysis, even for one gene or for empty/negative gene sets. Do not switch to grn-gene-info or grn-evidence-audit when the user is explicitly asking for trait/GWAS enrichment."
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

## Notes

- use this after `grn-perturbation`, `grn-regulon-compare`, or `grn-infer` when the user asks what processes or pathways are enriched
- if the user asks what GO terms are enriched among predicted targets from an inferred network, first call `grn-infer`, then call this skill on the returned target set
