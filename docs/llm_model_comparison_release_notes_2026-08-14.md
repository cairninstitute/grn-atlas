# LLM Model Comparison Notes for Release Blog

Date: Friday, August 14, 2026

This note captures the current external-LLM testing story for the GRN Atlas skill layer in a form that is easy to reuse in a release blog, release notes, or collaborator update.

## Short version

The current canonical repo status is:

- current documented skill inventory: **100 skills** (**99 callable + 1 overview/router**)
- current single-skill coverage audit: **100/100 skills covered** across **386** natural-language routing prompts
- latest GPT-5.4 single-skill rerun on Saturday, August 22, 2026: **383/386 PASS**
- latest GPT-5.4 orchestration rerun on Saturday, August 22, 2026: **111/111 PASS**

We also ran comparison passes with Nvidia Nemotron-3-Ultra through OpenRouter:

- historical completed paced expanded orchestration matrix: **79/99 PASS**
- latest Saturday, August 22, 2026 single-skill rerun: **255/258 PASS** before provider/model exit
- latest Saturday, August 22, 2026 orchestration rerun: **37/40 PASS** before provider/model exit

We also ran a targeted Nemotron single-skill diagnostic subset focused on the orchestration failure families and their overlapping neighboring skills:

- targeted single-skill subset: **36/38 PASS**
- pass rate: **94.7%**

Interpretation:

- GPT-5.4 shows that the current skill layer can be used cleanly across the full present workflow surface.
- Nemotron shows that the system is not limited to one model, while also exposing the workflow families that are still fragile on weaker orchestrators.
- The targeted Nemotron subset further suggests that many of the remaining Nemotron failures are orchestration-depth and synthesis problems rather than broad single-skill routing failures.

## Comparison table

| Model | Date | Suite | Result | Interpretation |
|---|---|---|---|---|
| GPT-5.4 | August 22, 2026 | Single-skill matrix | 383/386 PASS | current routing status on the 386-case live matrix |
| GPT-5.4 | August 22, 2026 | Orchestration matrix | 111/111 PASS | current orchestration status on the 111-question live matrix |
| GPT-5.4 | August 21, 2026 | Historical expanded orchestration matrix | 99/99 PASS | earlier completed expanded benchmark |
| Nemotron-3-Ultra | August 14, 2026 | Orchestration matrix | 50/59 PASS | portability / robustness comparison |
| Nemotron-3-Ultra | August 22, 2026 | Historical paced expanded orchestration matrix | 79/99 PASS | completed expanded portability probe; substantial but not clean support |
| Nemotron-3-Ultra | August 22, 2026 | Partial single-skill rerun | 255/258 PASS | later health-check rerun; provider/model exited before completion |
| Nemotron-3-Ultra | August 22, 2026 | Partial orchestration rerun | 37/40 PASS | later health-check rerun; provider/model exited before completion |
| Nemotron-3-Ultra | August 14, 2026 | Targeted single-skill subset | 36/38 PASS | routing diagnostic centered on orchestration miss families |

## What Nemotron was able to do

The Nemotron orchestration run succeeded on most of the matrix and handled many realistic chained workflows, including:

- RNAi design and screening pipelines
- perturbation plus enrichment chains
- many cross-species workflows
- provenance and export workflows
- first-pass petunia phenotype workflows
- collaborator-oriented analysis chains

That matters because it shows the GRN Atlas skill layer is a real workflow surface, not just a set of isolated one-off tools.

## What the targeted Nemotron single-skill subset showed

The targeted 38-case subset was built to answer a narrower question:

- are the orchestration misses mostly caused by single-skill routing ambiguity?
- or are they more often caused by failing to chain and synthesize correctly once several steps are required?

Result:

- **36/38 PASS**

Strong in the targeted subset:

- shared regulators
- input normalization
- dataset import
- combinatorial perturbation
- decision boundary / confidence boundary
- dsRNA and dsRNA screening
- phenotype targeting
- coverage reporting
- experiment prioritization / optimization

The clearest weak family in that subset was `grn-infer`:

- one case used the right tool but passed `HY5` instead of the expected stable ID `AT5G11260`
- one case hit a provider internal error rather than a deterministic routing miss

Interpretation:

- most of the weak orchestration families are not broadly broken at the single-skill level
- the remaining Nemotron gap is more often chain start, under-chaining, or weak final synthesis

## What Nemotron missed that GPT-5.4 handled cleanly

Nemotron failed 9 questions that GPT-5.4 passed:

| Q | Workflow family | Failure summary |
|---|---|---|
| 1 | Shared regulators | missed abstract shared-regulator start for TP53 and MYC |
| 24 | Inference comparison | weak chaining on GRNBoost2 vs GENIE3 overlap + gene follow-up |
| 39 | Input normalization | failed messy mixed-species normalization/import setup |
| 41 | Combinatorial perturbation | too shallow on pairwise knockout comparison |
| 51 | Weak-signal boundary | weak uncertainty / support-boundary explanation |
| 53 | Intervention tradeoff | weak dsRNA vs promoter-edit comparison |
| 54 | Phenotype + readiness | incomplete petunia regulator + RNAi support chain |
| 56 | Capability boundary | weak "can and cannot support" explanation for petunia intervention planning |
| 57 | Single vs double perturbation | weak comparative perturbation reasoning |

In the later paced 99-question expanded run on Saturday, August 22, 2026, the persistent fail set broadened to:

- Q3, Q24, Q36, Q40, Q43, Q50, Q53, Q54, Q56, Q60, Q65, Q66, Q67, Q71, Q72, Q76, Q77, Q78, Q81, Q83

Those 20 persistent fails cluster into these families:

| Family | Questions | Failure mode |
|---|---|---|
| overlap / comparison under-chaining | Q3, Q24 | model retrieved partial evidence but did not complete overlap follow-up, enrichment, or gene-info steps |
| phenotype-first petunia targeting | Q36, Q50, Q54, Q81, Q83 | model found candidates but did not consistently turn them into explicit RNAi-ready ranking or validation-plan output |
| intervention tradeoff / boundary explanation | Q53, Q56 | weak final planning synthesis and weak “what the atlas can and cannot support” framing |
| transferability / family-rescue synthesis | Q40, Q67 | weak cross-species transfer narrative, sometimes compounded by provider overload |
| motif / promoter / edit chaining | Q43, Q78 | motif-side tools were touched, but the full promoter-support/edit interpretation did not complete cleanly |
| import-first chained workflows | Q65, Q66, Q71, Q77 | hardest current Nemotron family; returned-id reuse and downstream chaining remain fragile |
| decision-boundary / calibration / counterfactual synthesis | Q60, Q72, Q76 | model called part of the workflow surface but did not satisfy the requested synthesis structure |

## Failure pattern

Observed failure buckets in the paced 99-question Nemotron run on Saturday, August 22, 2026:

- **20 persistent fails**
- **9 flaky passes** that failed first and passed on retry
- a mixed failure profile:
  - true under-chaining / synthesis misses
  - provider overload / immediate upstream failures
  - a small number of real workflow-path issues surfaced by the run

Notable runtime-path issues exposed by the expanded run:

- Q66 surfaced a real `grn-omics-import` runtime error
- Q76, Q77, and Q78 surfaced HTTP 404 workflow-path failures

So the expanded Nemotron result is not just “the provider fell over” and not just “the model reasoned poorly.” It is a mixed stress result that reveals both weaker orchestration behavior and a few chain-path issues worth hardening.

## What this says about the current system

Strong today:

- atlas-backed direct retrieval and network interpretation
- RNAi / dsRNA workflows
- perturbation plus enrichment chains
- provenance-aware workflows
- many cross-species and researcher-handoff workflows

Still more fragile on weaker orchestrators:

- abstract or underspecified starting prompts
- messy-import recovery before downstream analysis
- import-first returned-id chaining
- weak-signal and uncertainty-boundary questions
- tradeoff-heavy intervention comparisons
- phenotype-to-experiment planning in non-model species
- inferred-edge prompts that benefit from stronger stable-ID normalization

## Good release-blog framing

Accurate public framing:

- GRN Atlas now has a broad, tested skill layer for regulatory-network research workflows.
- The current repo status is 383/386 on the live GPT-5.4 single-skill matrix and 111/111 on the live GPT-5.4 orchestration matrix.
- We also tested the same workflow surface against Nemotron-3-Ultra through OpenRouter.
- Nemotron completed a historical paced 99-question expanded orchestration matrix at 79/99 pass, and a later Aug. 22 rerun reached 255/258 single-skill and 37/40 orchestration cases before provider/model exit.
- A targeted 38-case Nemotron single-skill diagnostic then passed 36/38, showing that many of the remaining weaknesses are in orchestration depth rather than basic skill selection.
- Those weaker-model misses were useful: they directly shaped frontmatter, workflow guidance, and skill-boundary improvements.

## Useful phrases for later writing

- "tested not only with deterministic harnesses, but with external LLM-driven tool use"
- "clean full-matrix GPT-5.4 performance on the current orchestration surface"
- "cross-model comparison with Nemotron-3-Ultra revealed the remaining weak spots in phenotype-first planning, import-first chaining, uncertainty framing, and intervention tradeoff reasoning"
- "the same skill layer can support both interactive UI use and agent-driven orchestration"
- "a targeted Nemotron single-skill diagnostic passed 36/38, suggesting the remaining gap is more about chaining and synthesis than raw tool routing"

## Source artifacts

- Current persistent in-repo audit artifact:
  - `.agents/skills/_test_llm_coverage_audit.json`
- Raw temporary rerun outputs and local `.run_logs/` artifacts were intentionally cleaned from the workspace after the summarized results were recorded in the docs and release materials.
