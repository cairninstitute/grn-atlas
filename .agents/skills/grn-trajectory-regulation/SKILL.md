---
name: grn-trajectory-regulation
description: "Use when the question is about time-series, pseudotime, or trajectory-resolved regulation. Supports trajectory driver analysis (via grn-trajectory-drivers) and pseudotime TF activity scoring (via grn-pseudotime-activity) when an imported dataset with contrasts is available. Falls back to readiness reporting without imported data."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---
