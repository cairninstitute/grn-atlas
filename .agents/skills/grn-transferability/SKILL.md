---
name: grn-transferability
description: Assess whether a gene-level conclusion or candidate identified in one species can be carried over to another species, with ortholog support, caveats, and suggested validation. Good for requests like 'does this transfer to mouse', 'can I generalize this from human to mouse', or 'how transferable is this claim'. Not the same as finding orthologs or conserved edges.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-transferability/scripts/run.py --gene-id TP53 --target-species mouse --intent network
backend/venv/bin/python .agents/skills/grn-transferability/scripts/run.py --gene-id AT5G11260 --target-species tomato --intent experiment
backend/venv/bin/python .agents/skills/grn-transferability/scripts/run.py --gene-id TP53 --target-species mouse --intent network --http http://localhost:8000
```

## Notes

- use this when the question is whether a candidate-level story transfers across species, not whether one exact edge is conserved
- if the output says transferability is limited, follow up with `grn-conservation` or target-species analysis instead of assuming the source result holds
