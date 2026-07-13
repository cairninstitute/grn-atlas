---
name: grn-dsrna-screen
description: "Batch dsRNA designability screen across a gene set or pathway. Ranks genes by off-target burden to identify the best RNAi targets. Optionally predicts downstream effects of silencing the set. Use for high-throughput RNAi experiment planning."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-dsrna-screen/scripts/run.py --gene-ids AT1G49720,AT5G11260,AT2G43010 --species arabidopsis
backend/venv/bin/python .agents/skills/grn-dsrna-screen/scripts/run.py --pathway-id GO:0009651 --species arabidopsis
```

### Parameters
- `--gene-ids` (optional) — comma-separated gene IDs to screen
- `--pathway-id` (optional) — pathway ID to screen all member genes
- `--species` (optional) — species name (inferred from first gene if omitted)
- `--k` (optional, default 21) — siRNA k-mer length
- `--design-window` (optional, default 250) — design window size (40–1000)
- `--no-predict-effect` — skip downstream effect prediction
- Must provide either `--gene-ids` or `--pathway-id`
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with ranked gene list (designable count, off-target burden, mean TPM) and optional predicted downstream effects of silencing the set.
