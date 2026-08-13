---
name: grn-upstream
description: "Predict which transcription factors best explain a gene set using hypergeometric enrichment of TF regulons. Use for upstream regulator analysis of differentially expressed genes or any gene list, especially prompts like 'which TFs best explain this set', 'upstream regulators of these DEGs', or 'regulate at least 3 of these genes'. Prefer this over grn-shared-regulators when the task is to rank explanatory upstream TFs for a gene set rather than just list overlap. If the prompt names a species such as 'in human', keep that species argument explicit."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-upstream/scripts/run.py --gene-ids "BAX,BCL2,CDKN1A,MDM2,GADD45A" --species human
```

### Parameters
- `--gene-ids` (required) — comma-separated gene IDs (e.g. differentially expressed genes)
- `--species` (optional) — species name (auto-detected from first gene if omitted)
- `--depth` (optional, default 1) — regulon depth (1=direct targets, 2=includes indirect)
- `--top` (optional, default 50) — max number of regulators to return
- `--min-overlap` (optional, default 2) — minimum overlap to report a TF
- `--min-confidence` (optional, default 0.0) — minimum edge confidence
- `--no-include-inferred` — exclude inferred edges
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with ranked list of predicted upstream regulators, each with p-value, FDR q-value, overlap genes, and coverage.

## Routing notes

- Use this skill for `upstream regulators of BAX, BCL2, and CDKN1A in human` style prompts.
- Prefer this over `grn-shared-regulators` when the user wants ranked explanatory upstream regulators for a multi-gene set, even if the wording says `common upstream regulators`.
- If the user explicitly specifies a species, pass that species through instead of relying on auto-detection.
