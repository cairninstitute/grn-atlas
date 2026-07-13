---
name: grn-diff-regulation
description: "Compare TF regulatory activity between two groups of conditions/tissues. Identifies TFs whose targets show differential expression consistent with their regulatory role. Available for arabidopsis, tomato, petunia."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-diff-regulation/scripts/run.py --species arabidopsis --group-a root --group-b inflorescence
backend/venv/bin/python .agents/skills/grn-diff-regulation/scripts/run.py --species petunia --tf-gene-id Peaxi162Scf00921g00011 --group-a seedling --group-b flower
backend/venv/bin/python .agents/skills/grn-diff-regulation/scripts/run.py --species tomato --group-a leaf --group-b fruit --top 10
```

### Parameters
- `--species` (required) — species name
- `--group-a` (required) — comma-separated tissue names for condition A
- `--group-b` (required) — comma-separated tissue names for condition B
- `--tf-gene-id` (optional) — specific TF to analyze (default: scan all TFs)
- `--min-fold-change` (optional, default 1.0) — minimum |log2FC| or activity score to report
- `--top` (optional, default 50) — max TFs to return
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with differentially active TFs ranked by activity score, each with expression fold changes, target concordance, and top differentially expressed targets.
