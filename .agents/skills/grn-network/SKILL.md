---
name: grn-network
description: "Explore the regulatory network neighborhood of a gene. Returns its regulators (transcription factors that control it) and targets (genes it regulates), with confidence scores and evidence sources. Use for network exploration, finding upstream regulators, or downstream targets."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-network/scripts/run.py --gene-id ENSG00000136997
```

### Parameters
- `--gene-id` (required) — Ensembl gene ID
- `--direction` (optional, default "both") — choices: both, regulators, targets
- `--min-confidence` (optional, default 0.3) — minimum confidence score
- `--no-include-inferred` (optional flag) — exclude inferred edges
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-network/scripts/run.py --gene-id ENSG00000136997 --http http://localhost:8000
```

### Output
JSON object with center gene info, lists of regulators and targets, each with confidence and evidence.
