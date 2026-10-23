---
name: grn-clonelab-sequence
description: "Parse authenticated FASTA/GenBank DNA or retrieve a strand-correct promoter from an indexed local genome using a Darwin gene ID. Use before molecular calculations when sequence identity must be established."
compatibility: Requires the GRN Atlas backend virtualenv or a running Darwin server.
---

Use `scripts/run.py --content '<FASTA or GenBank>' --topology linear`. For genome-backed
retrieval, use `scripts/run.py --species arabidopsis --gene-id AT2G46830` and optionally
set `--upstream` and `--downstream`; this requires `make clonelab-data`. Preserve accessions,
assemblies, intervals, and hashes. Never infer missing bases or silently substitute an ortholog.
