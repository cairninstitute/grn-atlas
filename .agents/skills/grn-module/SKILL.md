---
name: grn-module
description: "Detect co-regulated gene modules/communities in a species regulatory network using graph algorithms (leiden, louvain, infomap, label_propagation). Identifies hub TFs within each module."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-module/scripts/run.py --species arabidopsis
backend/venv/bin/python .agents/skills/grn-module/scripts/run.py --species human --algorithm louvain --top-modules 10
backend/venv/bin/python .agents/skills/grn-module/scripts/run.py --species tomato --gene-id Solyc05g007180.2
```

### Parameters
- `--species` (required) — species to analyze
- `--algorithm` (optional, default "louvain") — community detection algorithm: leiden, louvain, infomap, label_propagation
- `--gene-id` (optional) — find this gene's module specifically
- `--min-confidence` (optional, default 0.0) — minimum edge confidence
- `--no-include-inferred` — exclude inferred edges
- `--resolution` (optional, default 1.0) — resolution parameter for leiden/louvain
- `--top-modules` (optional, default 20) — max modules to return
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with detected modules, each with size, TF count, hub TF, and top member genes ranked by degree.
