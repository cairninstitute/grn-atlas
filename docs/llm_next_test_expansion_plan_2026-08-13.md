# LLM Next Test Expansion Plan

Date: August 13, 2026

Status: Partially implemented as of Thursday, August 13, 2026. Several items from this plan were folded into the expanded 347-case single-skill matrix and 59-question orchestration matrix; the remaining items should be treated as future expansion candidates rather than current gaps by default.

This note proposes the next set of LLM test expansions for the GRN Atlas. The focus is on increasing realism rather than simply adding more of the same narrow routing checks. The highest-value additions are question families that stress ambiguity handling, phenotype-first reasoning, messy user input, uncertainty communication, and tradeoff-aware planning.

## Expansion goals

The next wave of tests should answer four questions:

1. Can the LLM handle how researchers actually ask questions, not just atlas-native prompts?
2. Can it stay useful when the evidence is weak, incomplete, or conflicting?
3. Can it ingest messy user inputs and still recover the right workflow?
4. Can it compare plausible strategies rather than only execute one valid path?

## Priority order

1. Phenotype-first and intent-first questions
2. Weak-signal and uncertainty workflows
3. Messy dataset import and cleanup workflows
4. Experimental tradeoff and decision workflows
5. Non-model / applied-species workflows
6. Literature-grounded ideation and synthesis
7. Boundary and refusal-quality cases

---

## Family 1: Phenotype-first / intent-first questions

### Why add these

Researchers often start with a phenotype or design intent, not a gene ID. These tests should check whether the LLM can translate a phenotype question into the right atlas workflow.

### What this family should test

- literature-first ideation
- hit-list generation
- candidate ranking
- follow-up planning
- explicit uncertainty handling when phenotype-to-gene mapping is indirect

### Exact prompts to add

1. "Which genes are the best targets for changing flower color in petunia? Start with broad literature-guided suggestions, map them into atlas-supported petunia candidates, and rank the best intervention targets."

2. "I want to reduce anthocyanin pigmentation in petunia petals. Which genes should I evaluate first, and why?"

3. "For increasing drought tolerance in Arabidopsis, which regulators look like the best first intervention targets in the atlas?"

4. "I want a shortlist of genes most likely to change ABA signaling in Arabidopsis. Start broad, then narrow to the most atlas-supported candidates."

5. "Which petunia genes look like the best candidates for altering floral scent without starting from a predefined hit list?"

### Expected skill patterns

- `grn_literature_review`
- `grn_dataset_import` or mapping logic when a list is generated
- `grn_user_gene_set_analysis`
- `grn_candidate_triage`
- `grn_consensus_ranking`
- `grn_experiment_prioritization` or `grn_experiment_optimizer`

### Notes

These should be orchestration-heavy tests, not just single-skill prompts.

---

## Family 2: Weak-signal / uncertainty / negative-result workflows

### Why add these

Real analyses often do not produce a clean winner. The system should be tested on whether it degrades honestly and constructively.

### What this family should test

- communicating uncertainty
- identifying evidence gaps
- suggesting the next discriminating step
- avoiding false certainty

### Exact prompts to add

1. "I compared these petunia candidates for flower color change and none looks strongly separated. What does the current atlas evidence support, what does it not support, and what is the smallest next experiment that would reduce uncertainty?"

2. "For TP53, BAX, and MDM2, the evidence looks mixed. Which conclusion is safest to act on right now, and what evidence would overturn it?"

3. "I have a gene list for Arabidopsis stress response, but no strong upstream regulator is emerging. What are the most likely reasons, and what should I do next?"

4. "Audit the evidence for the TP53 to BAX relationship, state the confidence boundary, and tell me the most defensible next move if I need to act with incomplete evidence."

5. "If the atlas cannot support a strong conclusion about this petunia RNAi target, tell me that directly and give me the narrowest useful next validation step."

### Expected skill patterns

- `grn_evidence_audit`
- `grn_confidence_boundary`
- `grn_counterfactual_analysis`
- `grn_minimal_validation`
- `grn_validation_plan`

### Notes

These should explicitly grade for honest uncertainty language and not only tool choice.

---

## Family 3: Messy dataset import and cleanup

### Why add these

Real users paste mixed-quality data. Current coverage is too clean.

### What this family should test

- mixed identifiers
- synonyms and aliases
- one-per-line vs comma-separated vs malformed lists
- extra columns
- import-first workflow recovery

### Exact prompts to add

1. "Import this hit list and analyze it: TP53, bax, MDM2, tumor protein p53, CDKN1A."

2. "I pasted a messy DEG list from Excel. Please import it, map what you can, tell me what failed to map, and then run a first-pass atlas interpretation.\n\nGene,log2FC,padj\nTP53,2.1,0.001\nBAX,1.8,0.004\nBADROW,,\nCDKN1A,1.3,0.01\nP53,-0.4,0.7"

3. "Take this Arabidopsis hit list with one gene per line, map it, and identify the top upstream regulators.\nHY5\nPIF4\nABF1"

4. "Import this mixed-species list and tell me what can be analyzed cleanly in human versus Arabidopsis: TP53, AT5G11260, BAX, HY5."

5. "Map this petunia candidate list, keep track of ambiguous rows, and only then run the first-pass interpretation: AN2, JAF13, DFR, CHS."

### Expected skill patterns

- `grn_dataset_import`
- `grn_user_gene_set_analysis`
- `grn_upstream`
- `grn_candidate_triage`

### Single-skill prompts to add

1. "Import this messy gene list and tell me what mapped cleanly: TP53, bax, tumor protein p53, CDKN1A."

2. "Import this CSV-like DEG snippet and preserve the gene content field for downstream analysis."

### Notes

This family should include at least one case where the correct outcome is a partial import with explicit unmapped rows.

---

## Family 4: Experimental tradeoff and strategy comparison

### Why add these

Researchers need comparison, not just one next step.

### What this family should test

- dsRNA vs promoter editing
- single-gene vs combinatorial intervention
- low-budget vs higher-confidence follow-up
- specificity vs expected effect size

### Exact prompts to add

1. "For petunia flower-color control, compare dsRNA knockdown of JAF13 versus promoter editing of AN2. Which looks like the more practical first experiment under a modest budget?"

2. "For TP53, compare single-gene knockout versus double knockout with MYC. Which strategy is more likely to reveal broader downstream network effects?"

3. "In Arabidopsis ABA signaling, compare silencing ABF1, ABF2, and PIF4. Rank them by both dsRNA specificity and predicted downstream interpretability."

4. "If I only have 7 days and low budget, what is the best follow-up for these petunia color candidates? If I have 30 days and a medium budget, how does the answer change?"

5. "Compare observational expression-context review versus intervention-first RNAi follow-up for these petunia candidates. Which should happen first and why?"

### Expected skill patterns

- `grn_dsrna`
- `grn_dsrna_screen`
- `grn_perturbation`
- `grn_combinatorial_perturbation`
- `grn_experiment_optimizer`
- `grn_experiment_prioritization`
- `grn_promoter_edit_prioritization`
- `grn_crispr_design`

### Notes

These should grade for explicit comparison language, not just whether both branches were executed.

---

## Family 5: Non-model and applied-species workflows

### Why add these

Public differentiation likely depends on petunia and other non-model workflows, but the tests are still dominated by human and Arabidopsis.

### What this family should test

- petunia-first workflows
- species coverage awareness
- transfer from model to non-model systems
- RNAi readiness in applied contexts

### Exact prompts to add

1. "For petunia, identify candidate regulators of petal pigmentation, then assess whether RNAi follow-up is actually supported for those candidates."

2. "Start from Arabidopsis anthocyanin regulators and identify the best petunia follow-up candidates using orthology and atlas support."

3. "Can conclusions about HY5 in Arabidopsis be transferred to petunia? Explain what is supported and what is still uncertain."

4. "For petunia AN2, JAF13, and DFR, rank which candidate is most ready for RNAi follow-up and which is most likely to have interpretable downstream effects."

5. "Tell me honestly what the atlas can and cannot support today for petunia flower-color intervention planning."

### Expected skill patterns

- `grn_orthology`
- `grn_transferability`
- `grn_coverage_report`
- `grn_candidate_triage`
- `grn_experiment_optimizer`
- `grn_validation_plan`

---

## Family 6: Literature-grounded ideation and synthesis

### Why add these

The literature skill is important for early-stage ideation, but current automated coverage is still shallow.

### What this family should test

- broad search term formation
- extracting candidate gene families from literature
- bridging literature candidates into atlas-supported genes
- distinguishing direct phenotype evidence from background review material

### Exact prompts to add

1. "Use recent literature to identify the gene families most often implicated in flower-color control in petunia and related ornamentals, then map those ideas into atlas-supported petunia candidates."

2. "For TP53 and BAX, review recent external literature on their regulatory relationship, then integrate that with atlas evidence into a writing-ready summary."

3. "For petunia pigmentation control, use literature to generate a candidate list, then rank only the genes that can actually be grounded in the atlas."

4. "Search recent literature for regulators of anthocyanin accumulation, then tell me which of those ideas have the strongest support in petunia according to the atlas."

5. "Review external evidence for whether RNAi is a plausible intervention mode for the top petunia pigmentation regulators, then propose the most defensible first test."

### Expected skill patterns

- `grn_literature_review`
- `grn_candidate_triage`
- `grn_evidence_synthesis`
- `grn_consensus_ranking`
- `grn_counterfactual_analysis`

### Notes

At least one case should grade whether unmappable literature candidates are handled honestly rather than forced into false mappings.

---

## Family 7: Boundary, refusal-quality, and unsupported-analysis cases

### Why add these

A good research copilot needs clean boundaries, not just successful happy paths.

### What this family should test

- unsupported species
- unsupported analysis layers
- gene not found
- partial support only
- refusal quality when an action is not grounded

### Exact prompts to add

1. "Do full cell-type regulatory analysis for TP53 and BAX right now."  
   Expected behavior: use readiness tooling, explain missing layers clearly.

2. "Design a dsRNA for a species that is not RNAi-ready in the atlas and tell me exactly what is missing."

3. "Tell me the best wheat flower-color intervention target using the atlas."  
   Expected behavior: acknowledge species limitation, offer onboarding/readiness path.

4. "Find the regulatory network for NONEXISTENT_GENE_XYZ and rank its best RNAi target regions."  
   Expected behavior: fail cleanly at gene resolution.

5. "Prove that this petunia candidate will change flower color."  
   Expected behavior: avoid overclaiming causality; provide evidence boundary instead.

### Expected skill patterns

- `grn_celltype_regulation`
- `grn_trajectory_regulation`
- `grn_coverage_report`
- `grn_species_onboarding_plan`
- `grn_confidence_boundary`

---

## Recommended additions by harness type

### Add primarily to orchestration suite

- Family 1: phenotype-first / intent-first
- Family 2: uncertainty / negative result
- Family 4: tradeoff and strategy comparison
- Family 5: non-model applied workflows
- Family 6: literature-grounded ideation
- Family 7: refusal-quality / unsupported-analysis

### Add primarily to single-skill suite

- targeted dataset-import messiness
- targeted routing boundaries between:
  - `grn_upstream` vs `grn_shared_regulators`
  - `grn_regulon` vs `grn_network`
  - `grn_literature_review` vs planning/report skills
  - `grn_experiment_prioritization` vs `grn_experiment_optimizer`
  - `grn_transferability` vs `grn_conservation`

---

## Suggested first implementation batch

If only one batch is added next, the highest-value 10 prompts are:

1. "Which genes are the best targets for changing flower color in petunia? Start with broad literature-guided suggestions, map them into atlas-supported petunia candidates, and rank the best intervention targets."
2. "I compared these petunia candidates for flower color change and none looks strongly separated. What does the current atlas evidence support, what does it not support, and what is the smallest next experiment that would reduce uncertainty?"
3. "I pasted a messy DEG list from Excel. Please import it, map what you can, tell me what failed to map, and then run a first-pass atlas interpretation."
4. "For petunia flower-color control, compare dsRNA knockdown of JAF13 versus promoter editing of AN2. Which looks like the more practical first experiment under a modest budget?"
5. "For petunia, identify candidate regulators of petal pigmentation, then assess whether RNAi follow-up is actually supported for those candidates."
6. "Use recent literature to identify the gene families most often implicated in flower-color control in petunia and related ornamentals, then map those ideas into atlas-supported petunia candidates."
7. "Tell me honestly what the atlas can and cannot support today for petunia flower-color intervention planning."
8. "For TP53, compare single-gene knockout versus double knockout with MYC. Which strategy is more likely to reveal broader downstream network effects?"
9. "Do full cell-type regulatory analysis for TP53 and BAX right now."
10. "Import this mixed-species list and tell me what can be analyzed cleanly in human versus Arabidopsis: TP53, AT5G11260, BAX, HY5."

---

## Suggested grading additions

These new families need some grading dimensions that go beyond simple tool presence:

- did the answer explicitly state uncertainty when appropriate
- did the answer distinguish supported vs unsupported claims
- did the answer preserve partial-import failures instead of hiding them
- did the answer compare alternatives explicitly
- did the answer keep species boundaries straight
- did the answer avoid overclaiming causality from weak evidence

---

## Practical next step

Recommended next implementation order:

1. Add 5 phenotype-first orchestration prompts
2. Add 5 uncertainty / negative-result prompts
3. Add 5 messy-import prompts
4. Add 5 tradeoff prompts
5. Add 5 petunia / non-model prompts
6. Add 5 literature-grounded prompts
7. Add 5 boundary / refusal-quality prompts

That would add 35 high-value orchestration cases and a smaller companion set of 10 to 15 new single-skill routing cases.
