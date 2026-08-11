---
name: grn-user-gene-set-analysis
description: "Use when the researcher wants atlas analysis over a user-provided gene list or imported table, such as enrichment, upstream regulators, candidate triage, and a local subgraph. Good for prompts like 'analyze my hit list' or 'what does the atlas say about these genes?'. Usually follows grn-dataset-import if the input is messy or tabular."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-user-gene-set-analysis/scripts/run.py --gene-ids TP53,BAX,MDM2 --intent experiment
backend/venv/bin/python .agents/skills/grn-user-gene-set-analysis/scripts/run.py --file /path/to/hits.tsv --species arabidopsis --intent rnai
```

### Parameters
- `--gene-ids` — comma-separated atlas gene IDs or symbols already known to the atlas
- `--content` — inline gene list or tabular content
- `--file` — local file path to analyze
- `--species` — optional species override
- `--intent` — analysis intent (`experiment`, `network`, `rnai`, `traits`)
- `--top-terms` — top enrichment terms to return
- `--top-regulators` — top upstream regulators to return
- `--top-candidates` — top ranked candidates to return
- `--no-subgraph` — skip induced-network extraction
- `--filename` — optional source filename label
- `--http URL` — optional running GRN Atlas server

Provide either `--gene-ids` or one of `--content` / `--file`.

### Output

JSON object containing:
- import/mapping summary
- enrichment results
- upstream regulator analysis
- candidate triage
- induced subgraph
- evidence summaries for the lead candidates
