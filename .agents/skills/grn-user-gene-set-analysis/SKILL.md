---
name: grn-user-gene-set-analysis
description: "Use when the researcher wants the atlas to interpret a hit list directly: run first-pass analysis over a user-provided gene set or imported table, including enrichment, upstream regulators, candidate triage, and a local subgraph. Trigger on requests like 'analyze my hit list', 'what does the atlas say about these genes', 'triage these hits', or 'summarize this gene set biologically'. Prefer this over grn-research-brief when the user wants analysis results rather than a structured collaborator-ready brief. Prefer this over grn-dataset-import when the user wants analysis, even if light mapping is needed internally."
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

## Routing boundary

- Use this skill for **first-pass interpretation of a gene set**
- Use `grn-dataset-import` instead when the user mainly wants a **mapping/import report**
- Use `grn-research-brief` instead when the user explicitly wants a **structured brief, handoff, summary, plan, or collaborator-facing package**

### Output

JSON object containing:
- import/mapping summary
- enrichment results
- upstream regulator analysis
- candidate triage
- induced subgraph
- evidence summaries for the lead candidates
