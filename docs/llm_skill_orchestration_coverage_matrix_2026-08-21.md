# LLM skill + orchestration coverage matrix

Date: 2026-08-21

## Current coverage status

- Total skills in the GRN Atlas suite: 100
- Single-skill LLM coverage: 100/100 skills covered
- Single-skill case inventory: 386 total
  - 347 baseline cases
  - 39 supplemental cases
- Orchestration question inventory: 111 total
  - 59 legacy chained questions
  - 16 supplemental chained questions
  - 13 first expansion questions
  - 11 second-wave expansion questions
  - 12 August 22 expansion questions
- Coverage audit status:
  - `single_skill_missing = []`
  - `orchestration_tool_missing_from_surface = []`
  - `supplemental_chain_missing_new_tools = []`

Artifacts:

- [coverage audit JSON](/home/kjanik/grn-atlas-codex/grn-atlas/.agents/skills/_test_llm_coverage_audit.json)

Raw temporary rerun outputs and local `.run_logs/` artifacts were intentionally cleaned from the workspace after the summaries in this document were written. The canonical persistent artifact retained in-repo is the coverage audit JSON above.

## Hardening completed in this pass

1. Fixed orchestration bridge for `grn_omics_import` so `name` is no longer dropped during CLI translation.
2. Fixed `grn-omics-import` so matrix files are parsed into `gene_values` and `sample_names` before posting to `/api/v1/import/omics`.
3. Fixed `grn-perturbation-calibration` runner to send `perturbed_gene` to the backend.
4. Added richer orchestration trace capture (`tool_calls`, `final_answer`, per-question detail) to improve diagnosis.
5. Added orchestration grading support for alias-equivalent tool groups via `used_tools_all_any`.
6. Tightened orchestration guidance for:
   - import-first omics workflows
   - explicit inferred-edge requests
   - explicit pathway-enrichment requests
7. Reworded weak imported-dataset orchestration prompts to require use of returned `dataset_id` / `contrast_id`.

## Result summary from this pass

### GPT-5.4

- Single-skill smoke slice: 6/6 pass
- Supplemental weak-family orchestration slice (Q60-Q75): 16/16 pass after hardening
- Stress-expansion orchestration slices (Q76-Q99): 24/24 pass after hardening
- Full current single-skill rerun: 385/386 pass on Saturday, August 22, 2026
- Full current orchestration rerun: 111/111 pass on Saturday, August 22, 2026

### Nemotron-3-Ultra

- Single-skill smoke slice: 5/6 pass, with the one miss caused by provider overload
- Supplemental weak-family orchestration slice (Q60-Q75): 11/16 pass on first paced run
- Targeted reruns of the 5 misses with slower pacing and fixes:
  - Q67 pass
  - Q69 pass
  - Q70 pass
  - Q72 pass
  - Q74 pass
- Historical completed paced expanded orchestration matrix: 79/99 pass
  - 20/99 persistent fails
  - 9 retry-recovered flaky passes
- Latest Saturday, August 22, 2026 full-rerun attempt:
  - single-skill rerun reached 258 completed cases and passed 255/258 before provider/model exit
  - orchestration rerun reached 40 completed questions and passed 37/40 before provider/model exit

Interpretation:

- GPT-5.4 is currently clean on the full current 111-question orchestration matrix, including the hardened weak families and new stress chains.
- Nemotron can complete much of the same surface, and pacing reduces transient failures, but it is not clean on the expanded matrix.
- The remaining Nemotron gap is a mix of provider instability, under-chaining, and weak final synthesis on harder comparison / phenotype / import workflows.
- The one remaining GPT-5.4 single-skill miss from the full rerun (`subgraph: TP53<->E2F1`) was fixed in a targeted follow-up rerun later on Saturday, August 22, 2026.

## Functionality-area coverage matrix

| Functionality area | Covered skills | Single-skill coverage | Orchestration coverage |
| --- | --- | --- | --- |
| Core atlas discovery and context | `grn-species`, `grn-stats`, `grn-organism-overview`, `grn-benchmark-status`, `grn-species-onboarding-status`, `grn-atlas-overview` | Covered directly; examples include `grn-species` (10 cases), `grn-stats` (10), `grn-organism-overview` (1), `grn-benchmark-status` (1), `grn-species-onboarding-status` (1), `grn-atlas-overview` (1) | Q5, Q14, Q17, Q25, Q48, Q60, Q75 |
| Gene lookup, identity, and input cleanup | `grn-gene-search`, `grn-gene-info`, `grn-input-normalization`, `grn-dataset-import`, `grn-user-gene-set-analysis` | Covered directly; `grn-gene-search` (12), `grn-gene-info` (11), `grn-input-normalization` (2), `grn-dataset-import` (3), `grn-user-gene-set-analysis` (1) | Q39, Q42, Q44, Q52, Q59 |
| Network neighborhood, shared regulators, paths, subgraphs, and topology | `grn-network`, `grn-shared-regulators`, `grn-pathfinding`, `grn-subgraph`, `grn-network-patterns`, `grn-centrality` | Covered directly; `grn-network` (12), `grn-shared-regulators` (2), `grn-pathfinding` (10), `grn-subgraph` (10), `grn-network-patterns` (4), `grn-centrality` (9) | Q1, Q6, Q7, Q14, Q18, Q21 |
| Expression, coexpression, differential, and tissue/cell-state workflows | `grn-expression`, `grn-coexpression`, `grn-differential-expression`, `grn-diff-regulation`, `grn-tissue-coexpression`, `grn-celltype-compare`, `grn-celltype-upstream`, `grn-omics-import`, `grn-trajectory-drivers`, `grn-pseudotime-activity`, `grn-workflow`, `grn-trajectory-regulation`, `grn-celltype-regulation` | Covered directly; `grn-expression` (10), `grn-coexpression` (10), `grn-diff-regulation` (10), `grn-celltype-compare` (1), `grn-celltype-upstream` (1), `grn-omics-import` (1), `grn-trajectory-drivers` (1), `grn-pseudotime-activity` (1), `grn-workflow` (1), `grn-trajectory-regulation` (2), `grn-celltype-regulation` (2) | Q15, Q28, Q45, Q48, Q58, Q61, Q62, Q63, Q75 |
| Upstream regulators, regulons, activity scoring, and enrichment | `grn-upstream`, `grn-regulon`, `grn-regulon-compare`, `grn-regulon-enrichment`, `grn-enrichment`, `grn-pathway-activity`, `grn-pathway-enrichment`, `grn-tf-activity` | Covered directly; `grn-upstream` (6), `grn-regulon` (6), `grn-regulon-compare` (4), `grn-regulon-enrichment` (1), `grn-enrichment` (21), `grn-pathway-activity` (1), `grn-pathway-enrichment` (1), `grn-tf-activity` (1) | Q3, Q6, Q16, Q26, Q27, Q30, Q45, Q71, Q73 |
| Perturbation, cascade, and combinatorial intervention analysis | `grn-perturbation`, `grn-cascade`, `grn-combinatorial-perturbation` | Covered directly; `grn-perturbation` (14), `grn-cascade` (10), `grn-combinatorial-perturbation` (2) | Q8, Q12, Q19, Q41, Q49, Q57 |
| RNAi / dsRNA intervention design | `grn-dsrna`, `grn-dsrna-screen`, `grn-isoform-coverage`, `grn-sirna-pool` | Covered directly; `grn-dsrna` (15), `grn-dsrna-screen` (11), `grn-isoform-coverage` (1), `grn-sirna-pool` (1) | Q2, Q9, Q10, Q11, Q22, Q32, Q36, Q53, Q54, Q72 |
| CRISPR, promoter editing, variant overlap, and primer design | `grn-crispr-compare`, `grn-crispr-design`, `grn-crispr-offtargets`, `grn-variant-effect`, `grn-promoter-edit-prioritization`, `grn-primer-design` | Covered directly; each has direct single-skill coverage (`grn-crispr-compare` 1, `grn-crispr-design` 1, `grn-crispr-offtargets` 1, `grn-variant-effect` 1, `grn-promoter-edit-prioritization` 1, `grn-primer-design` 1) | Q47, Q53, Q66 |
| Motif, genome, and chromatin support | `grn-motif`, `grn-motif-query`, `grn-genome-browser`, `grn-chromatin-support`, `grn-peak-import` | Covered directly; `grn-motif` (10), `grn-motif-query` (1), `grn-genome-browser` (1), `grn-chromatin-support` (1), `grn-peak-import` (1) | Q43, Q47, Q64, Q65, Q68 |
| Inferred edges, modules, and signaling extensions | `grn-infer`, `grn-module`, `grn-ligand-receptor`, `grn-signaling-to-tf` | Covered directly; `grn-infer` (10), `grn-module` (10), `grn-ligand-receptor` (1), `grn-signaling-to-tf` (1) | Q23, Q24, Q27, Q28, Q29, Q69, Q70 |
| Orthology, conservation, transferability, and family rescue | `grn-orthology`, `grn-conservation`, `grn-transferability`, `grn-transfer-risk`, `grn-family-rescue` | Covered directly; `grn-orthology` (10), `grn-conservation` (10), `grn-transferability` (3), `grn-transfer-risk` (1), `grn-family-rescue` (1) | Q4, Q13, Q20, Q34, Q40, Q67 |
| Trait and phenotype interpretation | `grn-trait-association`, `grn-phenotype-targeting`, `grn-literature-review` | Covered directly; `grn-trait-association` (1), `grn-phenotype-targeting` (3), `grn-literature-review` (3) | Q36, Q46, Q50, Q55, Q73 |
| Evidence, confidence, ranking, and experiment planning | `grn-candidate-triage`, `grn-consensus-ranking`, `grn-evidence-audit`, `grn-evidence-synthesis`, `grn-confidence-boundary`, `grn-decision-boundary`, `grn-counterfactual-analysis`, `grn-hypothesis-compare`, `grn-coverage-report`, `grn-experiment-prioritization`, `grn-experiment-optimizer`, `grn-minimal-validation`, `grn-validation-plan` | Covered directly; each skill has single-skill tests, including `grn-candidate-triage` (2), `grn-consensus-ranking` (1), `grn-evidence-audit` (1), `grn-decision-boundary` (2), `grn-coverage-report` (2), `grn-experiment-prioritization` (2), `grn-experiment-optimizer` (2), `grn-minimal-validation` (1), `grn-validation-plan` (1) | Q30, Q31, Q32, Q33, Q34, Q37, Q38, Q51, Q54, Q56 |
| Reporting and collaborator handoff | `grn-research-brief`, `grn-study-packet`, `grn-study-report` | Covered directly; `grn-research-brief` (1), `grn-study-packet` (2), `grn-study-report` (2) | Q30, Q35, Q38 |
| Export, provenance, and citations | `grn-export`, `grn-provenance`, `grn-citations` | Covered directly; `grn-export` (14), `grn-provenance` (15), `grn-citations` (10) | Q17, Q18, Q25 |
| Perturbation import and calibration | `grn-perturbation-import`, `grn-perturbation-calibration` | Covered directly; each has direct single-skill coverage (1 each) | Q74 |

## Hardened weak-family questions

These were the orchestration families that needed work in this pass.

| Question ID | Family | GPT-5.4 after fix | Nemotron after pacing/fix |
| --- | --- | --- | --- |
| Q61 | imported dataset → cell-state compare → upstream | pass | pass |
| Q62 | imported dataset → trajectory drivers → pseudotime activity | pass | pass |
| Q63 | imported dataset → packaged import-to-activity workflow | pass | pass |
| Q68 | genome context + promoter motif evidence | pass | pass |
| Q69 | inferred targets + module agreement | pass | pass on targeted rerun |
| Q73 | pathway enrichment + trait association | pass | pass |
| Q74 | perturbation import + calibration | pass | pass on targeted rerun |

## Stress-chain expansion status

The expanded orchestration layer added 24 new chained questions intended to stress skill composition rather than just tool reachability. These cover:

- import → contrast → upstream / trajectory / packaged workflow chains
- CRISPR design + off-target + promoter / motif context
- inferred-edge validation against module structure
- pathway activity + trait / phenotype interpretation
- conservation + transferability + family-rescue chains
- phenotype-targeting + validation-planning chains

Result:

- GPT-5.4 full current matrix: 111/111 pass
- No GPT-5.4 residual failures remain in the stress-expansion layer after hardening
- Nemotron paced expanded matrix: 79/99 pass, with the largest failure concentration in phenotype-first planning, import-first chains, and comparison-heavy planning prompts

## Nemotron 99-question fail-family breakdown

Persistent fails in the paced Saturday, August 22, 2026 run:

- Fail IDs: Q3, Q24, Q36, Q40, Q43, Q50, Q53, Q54, Q56, Q60, Q65, Q66, Q67, Q71, Q72, Q76, Q77, Q78, Q81, Q83
- Flaky-pass IDs: Q4, Q22, Q38, Q39, Q46, Q70, Q75, Q82, Q99

Failure families:

| Family | Questions | Pattern |
| --- | --- | --- |
| Under-chaining on comparison workflows | Q3, Q24 | Model starts correctly but stops before overlap follow-up, gene-info lookup, or enrichment completion |
| Phenotype-first petunia planning and ranking | Q36, Q50, Q54, Q81, Q83 | Model finds candidates but often fails to convert them into explicit RNAi-ready prioritization, consensus ranking, or execution-ready planning |
| Applied intervention tradeoff reasoning | Q53, Q56 | Model calls part of the surface but misses explicit planner/optimizer framing or honest capability-boundary synthesis |
| Cross-species transfer / evidence framing | Q40, Q67 | Weak transferability/family-rescue synthesis, sometimes mixed with provider overload |
| Motif / promoter / edit workflow completion | Q43, Q78 | Starts the motif-side chain but fails to complete the required promoter/evidence/edit narrative; one branch also showed 404-style endpoint failure |
| Import-first chained workflows | Q65, Q66, Q71, Q77 | Hardest Nemotron family: import/returned-id chaining remains fragile; one case exposed a real runner/runtime issue in the omics-import chain |
| Activity / pathway / calibration style synthesis | Q60, Q72, Q76 | Calls some of the right tools but misses the exact multi-step synthesis boundary the prompt requires |

Error-mode notes:

- Provider overload / immediate upstream failures were still present in several persistent misses: Q40, Q43, Q50, Q53, Q56, Q67, Q71, Q83
- Endpoint / runner failures appeared in a smaller subset and are not just model weakness:
  - Q66 surfaced a real `grn-omics-import` runtime error
  - Q76, Q77, and Q78 surfaced HTTP 404 failures in the attempted workflow chain
- Retry helped materially but did not clean the matrix:
  - 9 questions recovered on retry
  - 20 questions still failed after retry

## Remaining practical limitation

The main residual limitation is no longer just raw provider stability. After paced execution and one retry per question, Nemotron still shows persistent weakness on:

- phenotype-first candidate grounding and ranking
- import-first workflows that require reusing returned ids across steps
- comparison-heavy intervention planning
- explicit decision-boundary and counterfactual synthesis

The skill surface is covered, and GPT-5.4 is clean on it, but Nemotron remains materially less reliable on the hardest chained workflows.
