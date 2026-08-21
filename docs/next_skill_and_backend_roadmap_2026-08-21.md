# Next Skills and Backend Capability Roadmap

Date: Friday, August 21, 2026

Purpose: define the next concrete expansion pass after the current 90-skill baseline, separating:

- new skills that would materially improve researcher-facing usefulness
- backend/data/method work that should be prioritized even when it does not require a new skill

This roadmap is intended to close the most important remaining research gaps after the current skill expansion and hardening work.

## Executive summary

The remaining gaps are no longer mostly about missing basic surfaces. The current stack already covers:

- atlas navigation
- candidate discovery and ranking
- network/regulon/pathway/trait/motif interpretation
- dsRNA workflows
- cross-species reasoning
- evidence/provenance/handoff surfaces

The next gap cluster is deeper:

1. stronger chromatin/cis-regulatory evidence integration
2. stronger CRISPR researcher workflow maturity
3. direct signaling evidence instead of proxy fallback
4. stronger cell-state and trajectory biological depth
5. better trust-calibrated literature-to-action mapping

## Roadmap structure

This roadmap is split into two tracks:

- Track A: next 10 skills worth adding
- Track B: backend/data/method work that should proceed even without adding new skills

The highest-value path is to implement both tracks in parallel where possible.

## Track A — next 10 skills to add

## A1. `grn-cis-support-audit`

Goal:

- give a single decision-ready view of whether a TF→target claim is supported by promoter motif, chromatin peak, enhancer linkage, and prior regulatory evidence

Why it matters:

- researchers need one place to judge whether a regulatory edge is merely plausible or genuinely cis-supported

Primary inputs:

- source TF
- target gene
- species

Expected output:

- promoter evidence
- motif support summary
- peak support summary
- enhancer/gene linkage support
- confidence tier
- explicit unsupported/missing layers

Dependencies:

- stronger chromatin linkage tables
- peak-to-gene support objects

Priority:

- very high

## A2. `grn-enhancer-network`

Goal:

- let researchers inspect a gene’s enhancer-linked regulatory neighborhood rather than only promoter-local reasoning

Why it matters:

- promoter-only logic is not enough once users ask for real regulatory mechanism support

Expected output:

- enhancer-linked regulators
- linked target genes
- evidence type per linkage
- exportable region-centered subnetwork

Dependencies:

- enhancer / peak-gene linkage ingestion

Priority:

- very high

## A3. `grn-peak-gene-linkage`

Goal:

- expose region→gene linkage directly as a first-class query rather than burying it inside broader chromatin tooling

Why it matters:

- users often want to ask a simple question: “what gene does this region likely regulate?”

Expected output:

- linked genes
- linkage score / evidence source
- overlapping motifs / TF support

Dependencies:

- imported or derived linkage layer

Priority:

- high

## A4. `grn-celltype-regulon`

Goal:

- extract and compare regulons in a chosen cell type or state, not just rank active TFs

Why it matters:

- researchers need state-specific target programs, not only state-specific regulator rankings

Expected output:

- state-specific regulon members
- overlap vs global regulon
- confidence / support summary

Dependencies:

- stronger cell-state datasets
- state-specific activity and filtering logic

Priority:

- very high

## A5. `grn-transition-drivers`

Goal:

- provide an explicit trajectory/branch driver surface for “what drives this transition?”

Why it matters:

- this question is common and should not depend on users knowing which lower-level trajectory tools to combine

Expected output:

- ranked transition drivers
- branch or contrast context
- supporting target programs
- comparison against static differential signals

Dependencies:

- stronger trajectory datasets
- robust pseudotime/branch metadata handling

Priority:

- high

## A6. `grn-crispr-vs-dsrna-compare`

Goal:

- compare RNAi and CRISPR intervention strategies for the same candidate genes and intent

Why it matters:

- users often care about the decision, not the modality in isolation

Expected output:

- specificity comparison
- implementation complexity
- expected network consequence framing
- recommended first intervention

Dependencies:

- stronger CRISPR scoring
- stable dsRNA comparison features

Priority:

- very high

## A7. `grn-edit-consequence`

Goal:

- predict likely regulatory/network consequences of a promoter edit, motif disruption, or coding edit

Why it matters:

- current editing tools are still too separated from downstream biological interpretation

Expected output:

- likely direction of effect
- affected regulator/target relationships
- downstream pathway/program expectations
- uncertainty statements

Dependencies:

- promoter/motif reasoning
- perturbation / cascade integration

Priority:

- very high

## A8. `grn-multiome-support-audit`

Goal:

- summarize whether a biological claim is supported across expression, chromatin, motif, perturbation, and prior atlas evidence

Why it matters:

- researchers increasingly want evidence triangulation, not single-layer scores

Expected output:

- layer-by-layer support table
- conflicting evidence summary
- evidence-weighted confidence

Dependencies:

- stronger multi-layer provenance normalization

Priority:

- high

## A9. `grn-literature-grounding`

Goal:

- improve the literature-to-atlas bridge by explicitly scoring how external paper terms were normalized into atlas-grounded candidates

Why it matters:

- current phenotype-first discovery works, but trust in homolog/family rescue still needs better explanation

Expected output:

- exact symbol matches
- synonym matches
- ortholog/family-level rescues
- confidence score for each mapping path

Dependencies:

- stronger synonym / ortholog / family normalization logic

Priority:

- high

## A10. `grn-intervention-strategy-ranker`

Goal:

- compare intervention modes across candidates: dsRNA, CRISPR knockout, promoter editing, motif disruption, validation-only follow-up

Why it matters:

- researchers need decision support across intervention classes, not only within one class

Expected output:

- ranked intervention options
- feasibility / specificity / confidence tradeoffs
- recommended first move under budget/timeline constraints

Dependencies:

- stronger CRISPR maturity
- edit consequence logic
- experiment optimizer integration

Priority:

- very high

## Track B — backend/data/method work that should proceed even without new skills

## B1. Direct signaling data ingestion

Problem:

- current signaling workflows are functional but still proxy-backed in important cases

Needed work:

- ingest ligand/receptor sources
- ingest receptor→TF bridge layers
- preserve evidence-mode distinctions between direct vs fallback

Why this is not just a new skill:

- the main missing piece is biological content, not interface surface

Priority:

- very high

## B2. Real single-cell benchmark ingestion

Problem:

- current cell-type workflows are benchmarked mainly through curated/proxy cases

Needed work:

- import real public benchmark datasets
- define accepted regulator sets
- benchmark against known lineage/state regulators

Why this is not just a new skill:

- the limiting factor is validation depth and data realism

Priority:

- very high

## B3. Real trajectory benchmark ingestion

Problem:

- current trajectory logic is stronger than before but still limited in biological grounding

Needed work:

- public developmental / state-transition datasets
- branch-aware benchmark cases
- stability checks under subsampling and pseudotime perturbation

Priority:

- high

## B4. Enhancer / peak-gene linkage layer

Problem:

- current chromatin reasoning is still promoter-weighted

Needed work:

- peak import normalization
- enhancer-gene linkage schema
- linkage confidence and provenance

Priority:

- very high

## B5. CRISPR engine maturation

Problem:

- CRISPR still lags dsRNA in workflow maturity

Needed work:

- gene-first locus retrieval
- stronger off-target search/ranking
- edit-intent modes
- comparison surfaces across strategies

Priority:

- very high

## B6. Perturbation-grounded calibration expansion

Problem:

- perturbation surfaces exist, but calibration against observed data is still relatively shallow

Needed work:

- import more perturbation datasets
- calibrate direction and ranking consistency
- expose disagreement classes

Priority:

- high

## B7. Literature normalization and trust scoring

Problem:

- phenotype-first literature workflows still depend on mapping across family labels, ortholog names, and non-atlas symbols

Needed work:

- stronger normalization graph
- confidence tiers for mapping path type
- explanation surfaces for exact vs inferred matches

Priority:

- high

## B8. Multi-modal import hardening

Problem:

- researchers increasingly arrive with scRNA, pseudobulk, ATAC, peak sets, DEG tables, and mixed metadata

Needed work:

- more robust import contracts
- mixed-modality schema validation
- reproducible import manifests

Priority:

- high

## B9. Non-model species transfer hardening

Problem:

- plant and non-model workflows remain highly valuable, but data completeness still varies by species

Needed work:

- transcriptome completeness checks
- family-rescue hardening
- homeolog / duplicate-aware transfer reasoning
- species readiness metrics tied to actual workflows

Priority:

- medium-high

## B10. Cross-layer confidence synthesis

Problem:

- many questions now require reasoning across evidence layers, but the confidence model is still distributed across multiple tools

Needed work:

- unify confidence calculations across:
  - network evidence
  - motifs
  - chromatin
  - expression
  - perturbation
  - literature

Priority:

- high

## Recommended execution order

## Phase 1 — highest immediate value

1. B4 enhancer / peak-gene linkage layer
2. A1 `grn-cis-support-audit`
3. B5 CRISPR engine maturation
4. A6 `grn-crispr-vs-dsrna-compare`
5. A7 `grn-edit-consequence`

Rationale:

- this closes the most visible mechanistic and intervention-design gaps first

## Phase 2 — biological depth and direct evidence

6. B1 direct signaling data ingestion
7. A8 `grn-multiome-support-audit`
8. B2 real single-cell benchmark ingestion
9. B3 real trajectory benchmark ingestion
10. A4 `grn-celltype-regulon`
11. A5 `grn-transition-drivers`

Rationale:

- this moves current “usable but thin” workflows into more defensible biological territory

## Phase 3 — trust and researcher decision support

12. B7 literature normalization and trust scoring
13. A9 `grn-literature-grounding`
14. B10 cross-layer confidence synthesis
15. A10 `grn-intervention-strategy-ranker`
16. B9 non-model species transfer hardening

Rationale:

- this improves confidence calibration and makes the system more decision-ready for real research use

## Success criteria

This roadmap is succeeding if researchers can do all of the following more defensibly than today:

- ask whether an edge is really cis-supported, not just motif-plausible
- compare RNAi and CRISPR as intervention choices for the same goal
- inspect direct signaling evidence rather than mostly pathway proxy fallback
- ask what drives a cell state or transition with stronger biological grounding
- understand how literature-first candidate ideas were translated into atlas-grounded actionable genes
- choose an intervention strategy across modalities with explicit tradeoffs

## Recommendation

If only one focused next expansion pass can be funded, the best next package is:

1. enhancer / cis-support layer
2. CRISPR maturity upgrade
3. direct signaling evidence ingestion

That package would produce the biggest visible improvement in practical researcher usefulness without diluting effort across too many partially-developed fronts.
