---
name: grn-subgraph
description: "Extract the induced regulatory subgraph for a set of genes. Returns all known regulatory interactions among the provided genes, useful for visualizing how a gene set is interconnected. Prefer this when the user explicitly provides 2 or more genes and asks for the edges or interactions among them, including two-gene prompts like 'show the regulatory edges between TP53 and MYC' or 'show the bidirectional interactions between TP53 and E2F1'. Use this instead of grn-pathfinding when the task is to show all direct edges among named genes rather than to find a route or causal path from one gene to another."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-subgraph/scripts/run.py --gene-ids AT1G01010,AT1G01020,AT1G01030
```

### Parameters
- `--gene-ids` (required) — comma-separated gene IDs
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-subgraph/scripts/run.py --gene-ids AT1G01010,AT1G01020 --http http://localhost:8000
```

### Output
JSON object with `nodes` (gene metadata) and `edges` (regulatory interactions among the input genes).
