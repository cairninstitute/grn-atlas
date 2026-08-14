# LLM Model Comparison Notes for Release Blog

Date: Friday, August 14, 2026

This note captures the current external-LLM testing story for the GRN Atlas skill layer in a form that is easy to reuse in a release blog, release notes, or collaborator update.

## Short version

The current clean repo status is based on GPT-5.4:

- single-skill matrix: **347/347 PASS**
- multi-skill orchestration matrix: **59/59 PASS**

We also ran a full comparison pass with Nvidia Nemotron-3-Ultra through OpenRouter:

- full orchestration matrix: **50/59 PASS**
- pass rate: **84.7%**

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
| GPT-5.4 | August 13, 2026 | Single-skill matrix | 347/347 PASS | clean current routing status |
| GPT-5.4 | August 13, 2026 | Orchestration matrix | 59/59 PASS | clean current orchestration status |
| Nemotron-3-Ultra | August 14, 2026 | Orchestration matrix | 50/59 PASS | portability / robustness comparison |
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

## Failure pattern

Observed failure buckets in the final 59-question Nemotron run:

- **3 zero-tool-call misses**
- **6 tool-selection / under-chaining / synthesis misses**
- **0 provider-collapse failures** in the final completed run

That last point is important: the final 59-question run did not fail because the provider fell over. It failed because the model more often missed the right starting skill, used too few skills, or failed to synthesize the required comparison or uncertainty framing.

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
- weak-signal and uncertainty-boundary questions
- tradeoff-heavy intervention comparisons
- phenotype-to-experiment planning in non-model species
- inferred-edge prompts that benefit from stronger stable-ID normalization

## Good release-blog framing

Accurate public framing:

- GRN Atlas now has a broad, tested skill layer for regulatory-network research workflows.
- The clean current repo status is 347/347 GPT-5.4 single-skill pass and 59/59 GPT-5.4 orchestration pass.
- We also tested the same workflow surface against Nemotron-3-Ultra through OpenRouter.
- Nemotron completed the full 59-question orchestration matrix at 50/59 pass, which was strong enough to validate broad portability while still revealing where weaker orchestrators struggle.
- A targeted 38-case Nemotron single-skill diagnostic then passed 36/38, showing that many of the remaining weaknesses are in orchestration depth rather than basic skill selection.
- Those weaker-model misses were useful: they directly shaped frontmatter, workflow guidance, and skill-boundary improvements.

## Useful phrases for later writing

- "tested not only with deterministic harnesses, but with external LLM-driven tool use"
- "clean full-matrix GPT-5.4 performance on the current workflow surface"
- "cross-model comparison with Nemotron-3-Ultra revealed the remaining weak spots in messy-input recovery, uncertainty framing, and intervention tradeoff reasoning"
- "the same skill layer can support both interactive UI use and agent-driven orchestration"
- "a targeted Nemotron single-skill diagnostic passed 36/38, suggesting the remaining gap is more about chaining and synthesis than raw tool routing"

## Source artifacts

- GPT-5.4 full clean orchestration matrix:
  - `.agents/skills/_test_results_llm_orchestration_matrix_full_clean3_2026-08-13.json`
- Nemotron full orchestration matrix:
  - `.run_logs/nemotron_full_orchestration_matrix_2026-08-14.json`
- Nemotron targeted single-skill subset:
  - `.run_logs/nemotron_targeted_single_subset_2026-08-14.json`
