---
name: grn-clonelab-sequence
description: "Parse and inspect authenticated FASTA or GenBank DNA records with topology, features, hashes, and provenance. Use before molecular calculations when sequence identity must be established."
compatibility: Requires the GRN Atlas backend virtualenv or a running Darwin server.
---

Use `scripts/run.py --content '<FASTA or GenBank>' --topology linear`. Preserve accessions and hashes. Never infer missing bases or silently substitute an orthologous sequence.
