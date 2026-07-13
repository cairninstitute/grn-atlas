---
name: grn-perturbation
description: "Predict the downstream effects of knocking out or overexpressing a gene. Uses signed regulatory path propagation to estimate which genes would be up- or down-regulated and by how much. Use for in-silico perturbation experiments."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-perturbation/scripts/run.py --gene-id ENSG00000136997
backend/venv/bin/python .agents/skills/grn-perturbation/scripts/run.py --gene-id ENSG00000136997 --action oe
```

### Parameters
- `--gene-id` (required) — Ensembl gene ID to perturb
- `--action` (optional, default "ko") — perturbation type: ko (knock-out) or oe (over-express)
- `--depth` (optional, default 4) — propagation depth
- `--min-confidence` (optional, default 0.0) — minimum edge confidence
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-perturbation/scripts/run.py --gene-id ENSG00000136997 --http http://localhost:8000
```

### Output
JSON object with predicted downstream effects: affected genes with predicted direction (up/down) and effect magnitude.
