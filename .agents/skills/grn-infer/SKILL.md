---
name: grn-infer
description: >
  Use for expression-inferred regulatory edges from GRNBoost2 or GENIE3,
  including predicted regulators, predicted targets, method comparison,
  and inferred edges with curated overlap. Good for prompts like 'what
  does GRNBoost2 predict', 'compare GRNBoost2 vs GENIE3', 'expression-based
  network', 'GENIE3 predictions for PIL5', or 'find
  inferred regulators of HY5'. If the user asks which TFs are predicted
  by both methods, or asks to look up the shared TFs after comparison,
  do not stop at inference; follow with grn-gene-info for the overlap.
  Not for curated network neighborhoods;
  use grn-network for known regulators or targets. Often followed by
  grn-gene-info, grn-network, grn-enrichment, or grn-diff-regulation.
parameters:
  - name: gene_id
    type: string
    description: Gene ID or symbol to query edges for
  - name: species
    type: string
    required: true
    description: "Species: arabidopsis, tomato, or petunia"
  - name: direction
    type: string
    default: both
    description: "Edge direction: regulators, targets, or both"
  - name: method
    type: string
    description: "Inference method filter: GRNBoost2, GENIE3, or omit for both"
  - name: min_importance
    type: number
    default: 0.01
    description: Minimum importance score threshold (feature importance, 0-1 range)
  - name: compare_curated
    type: boolean
    default: false
    description: Cross-reference with curated interactions to show overlap
  - name: top
    type: integer
    default: 50
    description: Maximum edges to return
---

# grn-infer

Query inferred regulatory edges predicted by GRNBoost2 and/or GENIE3 from
expression data. These edges complement the curated regulatory network but
are computational predictions — always clearly labeled as inferred.

## Usage

```bash
# Direct mode
backend/venv/bin/python .agents/skills/grn-infer/scripts/run.py \
  --species arabidopsis --gene-id AT5G11260

# HTTP mode
backend/venv/bin/python .agents/skills/grn-infer/scripts/run.py \
  --species arabidopsis --gene-id HY5 --compare-curated --http http://localhost:8000
```

## Workflow

- if the user asks for inferred regulators or inferred targets only, call this skill directly
- if the user asks to compare GRNBoost2 and GENIE3, call this skill for both methods rather than answering from one method alone
- if the user asks for metadata about the TFs or genes returned by the overlap, follow this with `grn-gene-info`
- if the user asks what biological processes or pathways the inferred targets control, follow this with `grn-enrichment`
- if the user asks whether inferred regulators or targets also appear in the curated network, follow this with `grn-network`
- if the user asks for the top inferred regulators and then asks whether they also appear in the curated network, do not stop after `grn-infer`; follow with `grn-network` for the curated validation step
- if the user asks whether inferred TFs differ across tissues or conditions, follow this with `grn-diff-regulation`

## Routing examples

- `what does GRNBoost2 predict for HY5` → call `grn-infer`
- `compare GRNBoost2 vs GENIE3 for AT3G24650, then look up the shared TFs` → call `grn-infer` for both methods, then `grn-gene-info`
- `what genes does PIL5 regulate according to GRNBoost2, and what GO terms are enriched` → call `grn-infer`, then `grn-enrichment`
- `which inferred regulators of HY5 also appear in the curated network` → call `grn-infer`, then `grn-network`
