---
name: grn-centrality
description: "Compute centrality metrics for genes in a regulatory network. Supports degree (out/in/total), betweenness, closeness, and eigenvector centrality. Identifies hub regulators and key network nodes."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-centrality/scripts/run.py --species human --metric out_degree --top 10
backend/venv/bin/python .agents/skills/grn-centrality/scripts/run.py --gene-ids "TP53,MYC,E2F1,NFKB1" --metric degree
```

### Parameters
- `--species` (optional) — species to analyze
- `--gene-ids` (optional) — comma-separated gene IDs (must provide species or gene-ids)
- `--metric` (optional, default "degree") — centrality metric: degree, in_degree, out_degree, betweenness, closeness, or eigenvector
- `--top` (optional, default 50) — max results to return
- `--min-confidence` (optional, default 0.0) — minimum edge confidence
- `--no-include-inferred` — exclude inferred edges
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with ranked list of genes by the selected centrality metric, each with gene ID, symbol, TF status, and score.
