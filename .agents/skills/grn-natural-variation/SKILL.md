---
name: grn-natural-variation
description: "Query which promoter variants across accessions gain or lose a TF binding site. Currently reports readiness status and existing motif infrastructure; full functionality requires a variant panel (e.g. 1001 Genomes for Arabidopsis). Use grn-allele-affinity for single-variant rescoring against the existing atlas."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python). Direct database access only.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
# Check readiness: what infrastructure exists, what's missing
backend/venv/bin/python .agents/skills/grn-natural-variation/scripts/run.py --status

# Query existing motif infrastructure for a gene's promoter
backend/venv/bin/python .agents/skills/grn-natural-variation/scripts/run.py \
  --gene-id AT5G11260 --species arabidopsis

# Query a specific TF-target pair's motif sites (potential variant impact points)
backend/venv/bin/python .agents/skills/grn-natural-variation/scripts/run.py \
  --source-id AT2G43010 --target-id AT5G11260
```

### Parameters
- `--status` — report readiness: what tables and data exist, what's needed
- `--gene-id` — query motif hits in a gene's promoter region
- `--source-id` / `--target-id` — query motif sites for a specific edge
- `--species` — filter to one species
- `--db` — path to the SQLite database

### Output
JSON with:
- `readiness` — what infrastructure exists and what's missing for full natural-variation analysis
- `motif_sites` — existing JASPAR motif hits in promoter regions (potential variant impact points)
- `variant_data` — status of variant panel availability per species

### Current status
The atlas has JASPAR motif scanning, promoter windows, and log-odds scoring
infrastructure. What is **missing** for full natural-variation analysis is a
multi-accession variant panel. When one is loaded, this skill will identify
which variants fall in motif-supported binding sites and predict gain/loss
of TF binding per accession.

For single-variant analysis against the existing reference, use
`grn-allele-affinity` instead.
