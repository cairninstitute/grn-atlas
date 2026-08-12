---
name: grn-dsrna
description: "Use for single-gene RNAi planning or dsRNA sequence analysis. Good for requests like 'design dsRNA for HY5', 'can I silence this gene with RNAi', or 'analyze this dsRNA for off-targets'. When the user also asks what silencing would do, what pathways would change, or how to validate the knockdown, do not stop at dsRNA design; follow with grn-perturbation, grn-network, and often grn-enrichment. For screening multiple genes or ranking candidates, use grn-dsrna-screen."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-dsrna/scripts/run.py --target-gene AT1G01010 --species arabidopsis
backend/venv/bin/python .agents/skills/grn-dsrna/scripts/run.py --sequence AUGCAUGCAUGCAUGCAUGCA
```

### Parameters
- `--sequence` (optional) — dsRNA sequence to analyze
- `--target-gene` (optional) — gene symbol/ID to design dsRNA for
- `--species` (optional) — species name (required with --target-gene if gene ID alone is ambiguous)
- `--k` (optional, default 21) — siRNA k-mer length
- Must provide either `--sequence` or (`--target-gene` + `--species`)
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-dsrna/scripts/run.py --target-gene AT1G01010 --species arabidopsis --http http://localhost:8000
```

### Output
JSON object with dsRNA analysis results including on-target and off-target gene hits, specificity scores, and (in design mode) the optimal dsRNA window sequence.
