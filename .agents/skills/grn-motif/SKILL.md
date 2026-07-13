---
name: grn-motif
description: "Query TF binding motif hits in gene promoters. Find what TFs may bind a gene's promoter, or which genes a TF may regulate via motif evidence. Cross-reference with known regulatory edges. Available for arabidopsis, tomato, petunia (JASPAR 2024)."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-motif/scripts/run.py --gene-id AT5G11260
backend/venv/bin/python .agents/skills/grn-motif/scripts/run.py --tf-gene-id AT5G47220 --species arabidopsis --top 20
backend/venv/bin/python .agents/skills/grn-motif/scripts/run.py --gene-id AT5G11260 --include-edge-support
```

### Parameters
- `--gene-id` (optional) — target gene: find TF binding motifs in its promoter
- `--tf-gene-id` (optional) — TF gene: find genes with its binding motif
- `--species` (optional) — species name (auto-detected from gene if omitted)
- `--max-pvalue` (optional, default 1e-4) — max motif hit p-value
- `--min-score` (optional, default 0.0) — min motif hit score
- `--include-edge-support` — cross-reference motif hits with known regulatory edges
- `--top` (optional, default 100) — max results to return
- `--http URL` (optional) — base URL of a running GRN Atlas server

Must provide `--gene-id` or `--tf-gene-id` (or both).

### Output
JSON with motif hits including TF identity, motif score, p-value, genomic coordinates, and optional regulatory edge support.
