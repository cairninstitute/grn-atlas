---
name: grn-evidence-audit
description: Use to audit what evidence supports a gene or regulatory edge before acting on it. Good for requests like 'what supports TP53→BAX', 'audit the evidence', or 'what evidence layers back this claim'. Often followed by grn-confidence-boundary or grn-evidence-synthesis.
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
