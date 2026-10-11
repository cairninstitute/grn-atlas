---
name: grn-biosafety-screen
description: "Use when the user wants an off-target / biosafety check of a dsRNA (or an RNAi target gene) across species, not just within one transcriptome. Good for prompts like 'is this dsRNA safe — does it hit other crops?', 'screen this RNAi construct for cross-species off-targets', 'would silencing this gene in tomato also hit petunia or Arabidopsis?', or 'check this spray dsRNA for drift risk'. Reports self off-targets in the intended crop and cross-species drift hits in every other atlas transcriptome, with an overall risk class, and explicitly lists which organisms are NOT screened (no transcriptome loaded). Prefer this over grn-dsrna / grn-dsrna-screen when the concern is cross-species safety rather than single-transcriptome designability. Requires transcriptomes (arabidopsis, tomato, petunia today)."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python) or a running GRN Atlas server. Run `make setup` then `make fetch` so transcript stores are present.
metadata:
  author: grn-atlas
  version: "1.0"
---

## grn-biosafety-screen

Inputs:
- `--sequence` the dsRNA to screen, OR `--target-gene-id` to design one in the intended species
- `--intended-species` the crop the construct is meant for (inferred from the target gene if omitted)
- optional `--k` (default 21), `--design-window` (default 250), `--top-hits` (default 10)

Output:
- `overall_risk` — none / low / moderate / high across all screened transcriptomes
- `species_screened` — per species: self vs cross-species, off-target gene counts, top hits, risk
- `species_not_screened` — atlas species with no transcriptome loaded
- `coverage_note` + `caveats` — what this screen does and does not cover

Honesty notes:
- This is k-mer sequence matching (a specificity heuristic), not a measured silencing outcome.
- Absence of a hit is NOT a safety guarantee — only that no match exists in the loaded
  transcriptomes. Non-target organisms (pollinators, humans, soil microbes, crops not in
  the atlas) are not assessed and are listed as unscreened.
