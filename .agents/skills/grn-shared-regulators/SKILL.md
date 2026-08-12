---
name: grn-shared-regulators
description: "Find transcription factors that regulate two or more target genes in common, with per-target activation or repression direction, confidence, and evidence. Use for prompts like 'what regulates both TP53 and MYC', 'find shared upstream TFs for this gene pair', or 'which regulators control all genes in this set'. Prefer this over repeated grn-network calls when the user explicitly wants shared or common regulators across multiple targets."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-shared-regulators/scripts/run.py --gene-ids TP53,MYC --species human
```

### Parameters
- `--gene-ids` (required) — comma-separated target gene IDs or symbols
- `--species` (optional) — species name, recommended when targets are symbols
- `--min-confidence` (optional, default 0.3) — minimum edge confidence to keep
- `--top` (optional, default 25) — maximum shared regulators to return
- `--no-include-inferred` (optional flag) — exclude inferred edges
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with the target genes analyzed, the shared regulators, and per-target edge details for each shared regulator including regulation direction, confidence, evidence sources, and PMIDs.
