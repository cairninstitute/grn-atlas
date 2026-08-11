---
name: grn-variant-effect
description: "Use when the user wants to know whether a promoter-region variant overlaps motif-supported regulatory sites for a gene. Good for prompts like 'does this SNP disrupt a TF site?' or 'which TFs might be affected by this promoter variant?'. Current implementation is overlap-based, not full allele-specific affinity rescoring."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---
