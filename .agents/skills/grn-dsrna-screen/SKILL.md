---
name: grn-dsrna-screen
description: "Use for dsRNA designability screening when the user wants ranking-style output such as off-target burden, best-window burden, or screen-level predicted effect. Trigger on prompts like 'screen ABF1, ABF2, and PIF4', 'compare these RNAi targets', 'rank by off-target burden', or even 'screen this one gene for burden fields'. Prefer this over grn-dsrna when the request is explicitly a screen or ranking task, even if only one gene is provided."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-dsrna-screen/scripts/run.py --gene-ids AT1G49720,AT5G11260,AT2G43010 --species arabidopsis
backend/venv/bin/python .agents/skills/grn-dsrna-screen/scripts/run.py --pathway-id GO:0009651 --species arabidopsis
```

## Workflow

- when the user compares multiple RNAi targets, call this before any single-gene dsRNA design skill
- if the user asks for screening results plus the screen-level predicted effect of the set, stay in `grn-dsrna-screen` because this skill already returns optional `predicted_effect`
- if the user asks what happens after silencing the best target, or asks for downstream effects of one selected winner, follow this with `grn-perturbation`
- if the user asks what processes or pathways are affected, follow perturbation with `grn-enrichment`
- mention which target looks most specific or has the lowest off-target burden when the request is comparative
- if the user says `screen` but only provides one gene, use `grn-dsrna-screen` or `grn-dsrna`; prefer `grn-dsrna` when the intent is pure design for that one gene, and prefer `grn-dsrna-screen` when the user still wants ranking-style fields like off-target burden or predicted effect

### Parameters
- `--gene-ids` (optional) — comma-separated gene IDs to screen
- `--pathway-id` (optional) — pathway ID to screen all member genes
- `--species` (optional) — species name (inferred from first gene if omitted)
- `--k` (optional, default 21) — siRNA k-mer length
- `--design-window` (optional, default 250) — design window size (40–1000)
- `--no-predict-effect` — skip downstream effect prediction
- Must provide either `--gene-ids` or `--pathway-id`
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with ranked gene list (designable count, off-target burden, mean TPM) and optional predicted downstream effects of silencing the set.

## Routing examples

- `screen ABF1, ABF2, and PIF4 for dsRNA designability` → call `grn-dsrna-screen`
- `screen ABF1, ABF2, and PIF4, then perturb the best target` → call `grn-dsrna-screen`, then `grn-perturbation`
- `screen ABF1, ABF2, and PIF4, then explain enriched processes for the winner` → call `grn-dsrna-screen`, then `grn-perturbation`, then `grn-enrichment`
- `screen AT1G49720 alone for off-target burden` → call `grn-dsrna-screen` or `grn-dsrna`
