---
name: grn-infer
description: >
  Query GRNBoost2/GENIE3-inferred regulatory edges from expression data.
  Returns predicted TF-target relationships ranked by importance score.
  These are computationally inferred (NOT experimentally validated) and
  should be interpreted with caution given limited sample sizes (18-29 samples).
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
