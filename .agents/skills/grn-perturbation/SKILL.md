---
name: grn-perturbation
description: "Use to predict downstream effects of knocking out, silencing, or overexpressing one or more genes in silico. Good for prompts like 'what happens if MYC is knocked out' or 'what genes change if HY5 is silenced'. Use after RNAi or dsRNA design when the user asks what genes, pathways, or regulators would change after silencing a target. Often follow with grn-enrichment to interpret affected genes."
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
