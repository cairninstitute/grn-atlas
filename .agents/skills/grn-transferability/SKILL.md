---
name: grn-transferability
description: Assess whether a gene-level claim or candidate can be transferred from the source species to a target species, including ortholog support, caveats, and validation steps.
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
