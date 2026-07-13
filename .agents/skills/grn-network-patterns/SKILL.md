---
name: grn-network-patterns
description: "Detect structural network motifs: feed-forward loops, autoregulation, and bi-fan patterns. Use to find regulatory circuit architectures in a gene set or species network."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-network-patterns/scripts/run.py --species human --types ffl,autoregulation
backend/venv/bin/python .agents/skills/grn-network-patterns/scripts/run.py --gene-ids "TP53,MYC,E2F1,NFKB1" --types ffl
```

### Parameters
- `--gene-ids` (optional) — comma-separated gene IDs to search within
- `--species` (optional) — species to search (must provide gene-ids or species)
- `--types` (optional, default "ffl,autoregulation,bifan") — comma-separated pattern types
- `--min-confidence` (optional, default 0.0) — minimum edge confidence
- `--limit` (optional, default 100) — max patterns to return
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with list of detected patterns (type, involved genes with roles, edges) and summary counts.
