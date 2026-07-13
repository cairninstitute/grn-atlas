---
name: grn-cascade
description: "Predict regulatory cascade effects from upstream interventions on a target gene. Simulates how changing transcription factor activity propagates through the network to affect a target gene's downstream targets. Use for cascade/propagation modeling distinct from general perturbation."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-cascade/scripts/run.py --target-gene TP53 --interventions "SIRT1:up:1.5,MDM2:down:0.5"
```

### Parameters
- `--target-gene` (required) — gene ID to predict cascade effects on
- `--interventions` (required) — comma-separated `tf_id:direction:magnitude` triples (direction: up/down)
- `--depth` (optional, default 3) — cascade propagation depth
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-cascade/scripts/run.py --target-gene TP53 --interventions "SIRT1:up:1.5" --http http://localhost:8000
```

### Output
JSON object with cascade effects (downstream genes affected, direction, magnitude, confidence) and summary statistics.
