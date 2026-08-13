---
name: grn-network
description: "Use for single-gene network neighborhood questions: upstream regulators, downstream targets, or the local signaling neighborhood of one gene. Prefer this for prompts like 'what are the downstream targets of ABF1' or 'all regulatory connections for NFKB1'. Use this instead of grn-regulon when the user wants the immediate neighbors of one gene rather than the full expanded regulon. Not for paths between two genes; use grn-pathfinding for causal chains or routes."
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
