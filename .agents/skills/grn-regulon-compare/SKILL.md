---
name: grn-regulon-compare
description: "Compare the regulatory programs of two transcription factors: shared targets, overlap size, Jaccard similarity, enrichment significance, and unique targets. Use for prompts like 'what targets do TP53 and NFKB1 share', 'how similar are these TFs', or 'compare their regulons and then interpret the shared target set with enrichment.'"
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-regulon-compare/scripts/run.py --tf-a TP53 --tf-b MYC
backend/venv/bin/python .agents/skills/grn-regulon-compare/scripts/run.py --tf-a TP53 --tf-b E2F1 --depth 2
```

### Parameters
- `--tf-a` (required) — first transcription factor gene ID
- `--tf-b` (required) — second transcription factor gene ID
- `--depth` (optional, default 2) — regulon expansion depth
- `--min-confidence` (optional, default 0.0) — minimum edge confidence
- `--no-include-inferred` — exclude inferred edges
- `--http URL` (optional) — base URL of a running GRN Atlas server

### Output
JSON with regulon sizes, overlap genes, Jaccard similarity, hypergeometric p-value, and unique-to-each-TF gene lists.
