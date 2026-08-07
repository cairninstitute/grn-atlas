---
name: grn-evidence-audit
description: Summarize what evidence layers support a gene or regulatory edge, including curated, inferred, motif, coexpression, pathway, and trait support, with confidence and coverage gaps.
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
---

## Examples

```bash
backend/venv/bin/python .agents/skills/grn-evidence-audit/scripts/run.py --scope gene --gene-id TP53
backend/venv/bin/python .agents/skills/grn-evidence-audit/scripts/run.py --scope edge --source-id TP53 --target-id BAX
backend/venv/bin/python .agents/skills/grn-evidence-audit/scripts/run.py --scope edge --source-id AT5G11260 --target-id AT2G43010 --species arabidopsis --http http://localhost:8000
```

## Notes

- `scope=gene` requires `--gene-id`
- `scope=edge` requires `--source-id` and `--target-id`
- `--debug` adds intermediate counts and coverage details
