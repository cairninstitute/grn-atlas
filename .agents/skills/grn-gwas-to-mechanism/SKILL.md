---
name: grn-gwas-to-mechanism
description: "Use when the user has a trait- or GWAS-associated gene and wants the regulatory story behind it, not just the association. Good for prompts like 'what's the regulatory mechanism behind this GWAS hit?', 'this gene is linked to drought tolerance — what regulates it and what does it control?', or 'turn this trait-associated gene into a mechanism sketch'. Chains the gene's documented trait associations, its upstream regulators (whose variation could drive the trait through it), and — if it is a TF — its downstream program, with each regulatory edge's curated (measured) sign shown where one exists (expression correlation is not asserted as a direction). Prefer this over grn-trait-association when the user wants mechanism (upstream + downstream wiring), and over grn-network when the entry point is a phenotype/trait rather than pure topology."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## grn-gwas-to-mechanism

Inputs:
- `--gene` atlas gene id or symbol (use `--species` to disambiguate a symbol)
- optional `--species`, `--min-confidence` (default 0.4), `--top` (default 15)

Output:
- `trait_associations` — documented GWAS/trait links with PMIDs
- `upstream_regulators` — TFs regulating the gene, with edge sign + evidence tier
- `downstream_program` — the gene's targets when it is a TF, with edge sign + evidence tier
- `interpretation` + `caveats` — how to read each section honestly

Honesty notes:
- Trait associations are statistical (SNP→mapped gene→trait), not mechanistic proof.
- Edge signs labeled `inferred` come from expression correlation, not curated direction.
