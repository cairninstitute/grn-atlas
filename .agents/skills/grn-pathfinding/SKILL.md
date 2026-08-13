---
name: grn-pathfinding
description: "Use when the question asks for a path, route, chain, or direct/indirect connection between two genes, such as 'path from TP53 to BAX', 'direct path from TP53 to TERT', or 'what route connects gene A to gene B'. Prefer this over grn-network whenever both a source and target gene are named and the task is connectivity rather than neighborhood lookup."
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
