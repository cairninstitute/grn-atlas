---
name: grn-celltype-regulation
description: "Find TF regulators active in a specific cell type or cluster from an imported dataset. Computes regulon overlap with expressed genes and ranks TFs by enrichment p-value. Requires an imported dataset (use grn-omics-import first). Without a dataset_id, falls back to readiness reporting."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---
