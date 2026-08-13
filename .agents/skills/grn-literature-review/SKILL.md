---
name: grn-literature-review
description: "Use when the question requires external literature beyond what is already stored in the atlas, such as recent support, contradiction, or paper-level context for a gene, regulatory edge, pathway, or phenotype. Good for prompts like 'what papers support TP53->BAX', 'what has been published recently about Arabidopsis drought regulators?', or phenotype-first ideation such as 'which genes are the best targets for changing flower color in petunia?'. Not a replacement for atlas evidence; pair with grn-evidence-audit, grn-evidence-synthesis, candidate ranking, or coverage checks when you need both views."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` to create the venv.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-literature-review/scripts/run.py --scope gene --gene-id TP53
backend/venv/bin/python .agents/skills/grn-literature-review/scripts/run.py --scope edge --source-id TP53 --target-id BAX --years-back 3
backend/venv/bin/python .agents/skills/grn-literature-review/scripts/run.py --scope phenotype --query "Arabidopsis drought tolerance regulators"
```

### Parameters
- `--scope` — `gene`, `edge`, `pathway`, or `phenotype`
- `--gene-id` — atlas gene ID for gene scope
- `--source-id` / `--target-id` — atlas gene IDs for edge scope
- `--query` — free-text query for pathway/phenotype scope
- `--species` — optional species hint
- `--years-back` — recency window
- `--max-results` — number of papers to return
- `--http URL` — optional running GRN Atlas server

### Output

JSON object containing:
- search term used against the external literature index
- papers classified as support / contradict / mention
- PMIDs / DOIs / Europe PMC links when available
- explicit atlas/external evidence boundary note

## Routing notes

- Use this first for broad phenotype-first prompts when the user starts from a trait or outcome rather than a defined gene list.
- In non-model species such as petunia, use this to generate candidate families or regulator ideas before mapping them into atlas-supported genes.
- When the user asks whether those phenotype-linked candidates are actually actionable in the atlas, follow with candidate ranking and/or coverage checks rather than stopping at papers.
