---
name: grn-dsrna
description: "Design or analyze dsRNA sequences for RNA interference (RNAi) gene silencing. Given a target gene, designs the most specific dsRNA window. Given a dsRNA sequence, predicts off-target silencing across the transcriptome. Use for RNAi experiment planning."
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
