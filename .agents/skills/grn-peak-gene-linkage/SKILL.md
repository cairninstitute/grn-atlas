---
name: grn-peak-gene-linkage
description: "Query which gene(s) a genomic region or chromatin peak likely regulates. Accepts a peak_id or genomic region (chr:start-end) and returns linked genes with scores and overlapping TF motifs."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---
