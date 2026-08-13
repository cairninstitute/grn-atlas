# Capability Expansion Implementation Spec

Date: August 13, 2026

Status: Implemented in the repo as of Thursday, August 13, 2026. This document now serves as the implementation record for the M1–M8 capability pass rather than a future-only spec.

This document turns the high-level capability roadmap into implementation-ready details: concrete deliverables, interfaces, validation criteria, and integration points for each milestone.

## Definition of done for the roadmap

The roadmap is considered complete when:

1. phenotype-first questions produce structured candidate outputs rather than loose emergent summaries
2. messy user input is normalized deterministically before downstream interpretation
3. uncertainty and evidence-boundary reporting is consistent across planning workflows
4. tradeoff questions produce explicit side-by-side strategy comparisons
5. non-model workflows expose clear support, transferability, and limitation boundaries
6. literature-grounded workflows distinguish literature cues from atlas-grounded candidates
7. cell-type and trajectory answers are either genuinely supported or explicitly reduced to actionable readiness output
8. collaborator-facing report products can package the above in reusable form

## Milestone implementation details

### M1. grn-input-normalization

Primary deliverables:

- new skill: `grn-input-normalization`
- script wrapper around current backend import logic
- richer normalized output contract
- routing updates in `grn-dataset-import`

Interface:

- `--content` or `--file` required
- `--species` optional
- `--filename` optional

Output contract:

- `input_type`
- `filename`
- `species_filter`
- `species_guess`
- `mixed_species_detected`
- `species_distribution`
- `mapped_gene_ids`
- `mapped_rows`
- `ambiguous_rows`
- `unmapped_rows`
- `duplicate_inputs`
- `normalization_summary`
- `recommended_next_skill`
- `warnings`

Validation:

- plain list with aliases
- comma/semicolon separated lists
- CSV DEG snippet
- mixed-species list
- duplicate rows
- empty input

Integration points:

- `grn-dataset-import`
- future `grn-phenotype-targeting`
- future UI import/paste flows

### M2. grn-phenotype-targeting

Primary deliverables:

- new skill: `grn-phenotype-targeting`
- phenotype parsing templates
- candidate generation stages
- intervention-readiness summary

Expected internal composition:

- `grn-literature-review`
- `grn-candidate-triage`
- `grn-consensus-ranking`
- `grn-coverage-report`
- `grn-experiment-prioritization`

Output contract:

- phenotype summary
- literature cues
- atlas-grounded candidates
- ranking table
- support boundary
- next recommended follow-up mode

Validation:

- petunia flower color
- Arabidopsis ABA signaling
- pigment/anthocyanin regulator prompts

### M3. grn-decision-boundary

Primary deliverables:

- new skill: `grn-decision-boundary`
- standardized evidence-boundary output

Expected internal composition:

- `grn-evidence-audit`
- `grn-confidence-boundary`
- `grn-counterfactual-analysis`
- `grn-minimal-validation`

Output contract:

- supported now
- unsupported now
- ambiguous now
- overturn conditions
- smallest next validation move

Validation:

- mixed-evidence human candidate set
- weak petunia RNAi support
- no-clean-winner candidate set

### M4. Tradeoff-aware experiment planning

Primary deliverables:

- enhanced `grn-experiment-optimizer`
- enhanced `grn-experiment-prioritization`
- explicit strategy comparison mode

Output contract additions:

- side-by-side strategies
- scoring dimensions
- constraint-aware rationale
- recommended first action and fallback action

Validation:

- JAF13 dsRNA vs AN2 promoter edit
- low-budget vs medium-budget plan changes
- combo vs single perturbation tradeoff

### M5. Non-model strengthening

Primary deliverables:

- improved petunia/non-model ranking and transferability flows
- explicit “safe to infer / unsafe to infer” sections

Likely modified skills:

- `grn-transferability`
- `grn-coverage-report`
- `grn-candidate-triage`
- `grn-validation-plan`

Validation:

- Arabidopsis to petunia transfer
- petunia flower-color RNAi readiness
- non-model support boundary summaries

### M6. Literature-grounded synthesis

Primary deliverables:

- improved family-level extraction in `grn-literature-review`
- mapped vs unmapped candidate distinction
- atlas-grounded candidate section

Validation:

- phenotype-first literature prompts
- edge-support literature prompts
- petunia family mapping prompts

### M7. Cell-type / trajectory readiness-plus

Primary deliverables:

- stronger readiness reporting
- explicit missing-layer taxonomy
- future onboarding guidance

Validation:

- unsupported full-analysis requests
- readiness planning requests

### M8. Artifact/report products

Primary deliverables:

- stronger structured study/report products with:
  - phenotype-first sections
  - uncertainty sections
  - strategy-comparison sections
  - species limitation sections

Validation:

- collaborator handoff for petunia phenotype workflow
- uncertainty-aware experiment brief
- strategy comparison report

## Validation framework for each milestone

Each milestone should add:

1. single-skill routing tests
2. orchestration tests
3. direct CLI smoke checks
4. HTTP-mode smoke checks where applicable

Each milestone should also include:

- supported-case validation
- partial-support validation
- unsupported-case validation

## Recommended implementation order

1. `grn-input-normalization`
2. `grn-phenotype-targeting`
3. experiment comparison enhancements
4. `grn-decision-boundary`
5. non-model strengthening
6. literature-grounded synthesis improvements
7. readiness-plus for cell-type/trajectory
8. artifact/report enhancements
