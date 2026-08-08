---
name: grn-conservation
description: "Use when comparing whether regulatory edges or regulatory programs are conserved between species, such as 'is TP53→BAX conserved in mouse' or 'which HY5 edges are shared between Arabidopsis and tomato'. Focuses on conserved versus species-specific regulation across ortholog context. Not for just finding ortholog genes; use grn-orthology first if the cross-species counterpart is unknown."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-conservation/scripts/run.py --gene-ids AT1G01010,AT1G01020 --species-b human
```

## Workflow

- use this directly when the user already names the source gene or genes and target species
- for a single-gene question like `is TP53 conserved in mouse`, still call this skill with that one gene ID rather than starting with `grn-gene-search`
- if the ortholog is not known, first call `grn-orthology`, then call this skill on the resolved cross-species pair or gene set
- if the user asks whether a conclusion generalizes across species, follow this with `grn-transferability`

### Parameters
- `--gene-ids` (required) — comma-separated gene IDs (species A)
- `--species-b` (required) — species to compare against
- `--http URL` (optional) — base URL of a running GRN Atlas server

### HTTP mode

```bash
backend/venv/bin/python .agents/skills/grn-conservation/scripts/run.py --gene-ids AT1G01010,AT1G01020 --species-b human --http http://localhost:8000
```

### Output
JSON object with regulatory edges and their conservation status (conserved vs. species-specific) between the two species.
