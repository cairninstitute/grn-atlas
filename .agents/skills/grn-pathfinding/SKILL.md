---
name: grn-pathfinding
description: "Use when the question asks how one gene regulates another through a path or chain, such as 'path from TP53 to BAX', 'direct vs indirect regulation', or 'what route connects gene A to gene B'. Finds regulatory paths between two genes with per-step confidence and evidence. Not for general neighborhood lookup; use grn-network for regulators or targets of one gene."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-pathfinding/scripts/run.py --source ENSG00000136997 --target TP53
```

### Parameters
- `--source` (required) — source gene Ensembl ID
- `--target` (required) — target gene symbol
- `--max-depth` (optional, default 3) — maximum path length
- `--limit` (optional, default 20) — max number of paths to return
- `--min-confidence` (optional, default 0.3) — minimum edge confidence
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-pathfinding/scripts/run.py --source ENSG00000136997 --target TP53 --http http://localhost:8000
```

### Output
JSON object with list of regulatory paths, each containing steps with gene IDs, symbols, confidence, and evidence.
