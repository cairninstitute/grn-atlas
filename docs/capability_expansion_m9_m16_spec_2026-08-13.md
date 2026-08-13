# Capability Expansion M9–M16 Implementation Spec

Date: August 13, 2026

This document extends the capability expansion work beyond M8. The focus is the next set of weak-but-high-value workflow areas identified after the M1–M8 implementation pass.

## Objective

Strengthen the atlas skill layer in the places where researchers still hit practical limits:

1. non-model and transfer workflows
2. broader phenotype-first targeting
3. execution-grade experiment design
4. literature grounding precision
5. combinatorial perturbation reasoning
6. richer import and normalization behavior
7. stronger collaborator-facing outputs
8. deeper cell-type / trajectory readiness and future support boundaries

## Definition of done

The M9–M16 phase is complete when:

1. non-model transfer outputs separate exact ortholog, family analog, and unsupported claims
2. phenotype-first targeting supports more than the initial pigment-focused workflows
3. experiment planning returns execution-ready sections rather than only ranked strategies
4. literature outputs distinguish direct atlas-grounded candidates from family cues and unresolved mentions more cleanly
5. combinatorial perturbation outputs explain when a combination is worth more than the best single-gene intervention
6. import workflows handle more realistic DEG / spreadsheet-like pasted input
7. collaborator packet/report outputs clearly separate uncertainty, methods, limitations, and next actions
8. cell-type and trajectory outputs expose more explicit readiness and onboarding guidance while staying honest about unsupported analysis

## Milestones

### M9. Non-model / transfer strengthening

Primary deliverables:

- enhance `grn-transferability`
- enhance `grn-phenotype-targeting`
- add family-level and analog-style rescue sections

Output additions:

- `exact_ortholog_support`
- `family_level_analog_candidates`
- `best_available_analogs`
- `transfer_modes_considered`
- `unsupported_extrapolations`

Validation:

- Arabidopsis regulator to petunia analog case
- exact human-to-mouse ortholog case
- no-ortholog available case

### M10. Phenotype-first expansion

Primary deliverables:

- expand `grn-phenotype-targeting`
- add phenotype vocabulary / domain templates
- add more explicit intent-aware ranking/routing

Initial phenotype domains:

- pigmentation / color
- drought / ABA
- flowering time
- scent / volatile production
- growth / architecture

Output additions:

- `phenotype_domain`
- `candidate_generation_mode`
- `ranking_profile`

Validation:

- petunia color
- Arabidopsis drought/ABA
- flowering-time prompt
- scent prompt

### M11. Experiment-design outputs

Primary deliverables:

- enhance `grn-experiment-optimizer`
- enhance `grn-study-packet`
- enhance `grn-study-report`

Output additions:

- `execution_design`
- `recommended_controls`
- `suggested_readouts`
- `replicate_heuristics`
- `success_criteria`
- `failure_modes`

Validation:

- RNAi follow-up for petunia
- low-budget Arabidopsis validation
- promoter-edit style follow-up

### M12. Literature grounding precision

Primary deliverables:

- improve `grn-literature-review`
- improve family/gene extraction and grounding summaries

Output additions:

- `evidence_classes`
- `direct_perturbation_candidates`
- `mechanistic_family_cues`
- `species_mismatch_candidates`
- `grounding_summary`

Validation:

- phenotype-first literature prompt
- direct edge support prompt
- contradiction-heavy prompt

### M13. Combinatorial perturbation strengthening

Primary deliverables:

- enhance `grn-combinatorial-perturbation`
- connect combo outputs to single-gene baselines

Output additions:

- `single_gene_baseline`
- `combination_gain_summary`
- `redundancy_signals`
- `combo_recommended_next_step`

Validation:

- TP53 + MYC vs TP53 alone
- pairwise vs triple combo comparison

### M14. Import / normalization expansion

Primary deliverables:

- enhance `grn-input-normalization`
- improve import schema inference

Output additions:

- `detected_columns`
- `column_role_guess`
- `deg_schema_guess`
- `ambiguous_identifier_review`
- `suggested_species_filter`

Validation:

- realistic DEG snippet
- spreadsheet-like mixed columns
- species-mixed alias list

### M15. Collaborator-grade report refinement

Primary deliverables:

- enhance `grn-study-packet`
- enhance `grn-study-report`

Output additions:

- `audience_mode`
- `methods_and_provenance_summary`
- `species_limitations_summary`
- `decision_summary`
- `handoff_variants`

Validation:

- lab handoff packet
- decision memo style report
- uncertainty-heavy non-model report

### M16. Cell-type / trajectory readiness-plus

Primary deliverables:

- enhance `grn-celltype-regulation`
- enhance `grn-trajectory-regulation`
- add stronger onboarding guidance and honest support boundaries

Output additions:

- `onboarding_priority_layers`
- `minimal_dataset_requirements`
- `readiness_to_analysis_gap`
- `future_enabled_workflows`

Validation:

- unsupported single-cell request
- unsupported pseudotime request
- readiness-planning request

## Files expected to change

- `.agents/skills/grn-transferability/scripts/run.py`
- `.agents/skills/grn-phenotype-targeting/scripts/run.py`
- `.agents/skills/grn-literature-review/scripts/run.py`
- `.agents/skills/grn-experiment-optimizer/scripts/run.py`
- `.agents/skills/grn-combinatorial-perturbation/scripts/run.py`
- `.agents/skills/grn-input-normalization/scripts/run.py`
- `.agents/skills/grn-study-packet/scripts/run.py`
- `.agents/skills/grn-study-report/scripts/run.py`
- `.agents/skills/grn-celltype-regulation/scripts/run.py`
- `.agents/skills/grn-trajectory-regulation/scripts/run.py`
- `.agents/skills/_grn-common/scripts/research_workflows.py`
- targeted LLM test manifests / orchestration harness files

## Validation framework

Each milestone should have:

1. direct CLI smoke validation
2. targeted single-skill LLM validation
3. targeted orchestration validation where the milestone changes routing or composition

## Recommended implementation order

1. M9 + M10 together
2. M11 + M15 together
3. M12
4. M13
5. M14
6. M16
