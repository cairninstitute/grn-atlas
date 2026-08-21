# GRN Atlas Post-Release Hardening Plan

Date: Friday, August 21, 2026

Purpose: define the next phase of work after release now that the current milestone validation suite is clean. This plan is for deeper biological benchmarking, stronger method comparisons, richer data layers, and UI-level validation that are valuable but not required to ship the current release.

## Scope

This plan assumes:

- the current release branch has already passed the implemented validation suite
- remaining work is no longer about fixing failing milestone benchmarks
- remaining work is about increasing trust, depth, and external comparability

## Post-release goals

1. increase biological confidence beyond the current internal and proxy benchmarks
2. reduce reliance on fallback or heuristic-only modes where stronger data could exist
3. add UI-level validation for benchmark/report surfaces
4. improve external-method comparability for experimental design tooling
5. expand the benchmark corpus so future regressions are caught earlier

## Workstream overview

| Workstream | Focus | Priority | Why it matters |
|---|---|---:|---|
| PR1 | Validation dashboard and artifact schema hardening | High | closes the gap between backend benchmark generation and user-facing trust surfaces |
| PR2 | External comparator studies for dsRNA and CRISPR | High | moves design tooling from internal heuristics toward defensible comparative performance |
| PR3 | Real single-cell and trajectory benchmark expansion | High | upgrades current pass status from proxy validation to stronger biological validation |
| PR4 | Direct signaling data expansion | High | reduces dependence on pathway-proxy fallback for signaling → TF workflows |
| PR5 | TF/pathway activity benchmark expansion | Medium | broadens beyond TP53 and reduces overfitting to a narrow benchmark family |
| PR6 | Species-specific biological gold standards | Medium | strengthens plant/non-model confidence where researcher trust matters most |
| PR7 | Release-grade benchmark governance | Medium | keeps validation artifacts reproducible and interpretable over time |

## PR1–PR7 execution snapshot

| Workstream | Implementation status | Execution status | Evidence | Main note |
|---|---|---|---|---|
| PR1 | Complete | Pass | validation dashboard API/UI tests, schema validator | artifact-health warnings now surface explicitly |
| PR2 | Complete | Pass | `benchmark_rnai_comparator`, `benchmark_crispr_comparator` | comparator-style curated expectations, not live third-party parity runs |
| PR3 | Complete | Pass | `benchmark_celltype_regulation`, `benchmark_trajectory_workflows` | corpus-backed proxy cases now wired; real public datasets still remain a future strengthening step |
| PR4 | Complete | Pass | `benchmark_signaling_to_tf` | workflow passes, but direct human signaling coverage is still sparse and fallback-backed |
| PR5 | Complete | Pass | expanded TF/pathway activity benchmarks | broadened beyond TP53 to MYC, RELA, STAT1, HIF1A |
| PR6 | Complete | Pass | `benchmark_species_gold_standards` | petunia, tomato, arabidopsis, and human threshold checks passed |
| PR7 | Complete | Pass | manifest metadata, schema validation, post-release runner | benchmark artifacts are now versioned, traceable, and comparable across runs |

## PR1 — Validation dashboard and artifact schema hardening

Current state:

- benchmark/status artifacts exist and refresh cleanly
- dashboard/backend artifact layer is operational
- no dedicated UI snapshot/schema test layer exists yet

Objectives:

- validate artifact file schemas before dashboard consumption
- test missing-artifact states explicitly
- test dashboard rendering against representative benchmark states

Implementation:

- add JSON schema checks for:
  - `backend/data/validation_runs/latest_summary.json`
  - each `backend/data/validation_runs/benchmark_*.json`
  - legacy reports consumed by benchmark status surfaces
- add UI/component tests for:
  - complete benchmark state
  - missing one benchmark file
  - malformed benchmark file
  - stale benchmark timestamps
- add a small fixture pack under frontend test assets

Validation:

- schema validation must fail on malformed or incomplete benchmark artifacts
- dashboard tests must pass for complete state and render explicit warnings for degraded states

Success criteria:

- malformed artifacts are caught before rendering
- dashboard never silently drops benchmark sections
- degraded-state rendering has regression coverage

## PR2 — External comparator studies for dsRNA and CRISPR

Current state:

- dsRNA and CRISPR surfaces now pass internal validation
- current validation is still mostly heuristic/internal

Objectives:

- compare GRN Atlas outputs to accepted external tools
- identify where heuristics are strong enough and where they diverge

Implementation:

- assemble a benchmark panel of target sequences and expected design scenarios
- compare GRN Atlas dsRNA outputs against specialized RNAi tooling:
  - specificity burden
  - window placement
  - isoform coverage behavior
- compare GRN Atlas CRISPR outputs against external guide tools:
  - valid guide recovery
  - off-target burden ordering
  - strategy-level differences for KO / CRISPRi / CRISPRa

Validation:

- generate structured comparison reports with case-by-case deltas
- classify discrepancies into:
  - acceptable heuristic difference
  - implementation bug
  - unsupported advanced model feature

Success criteria:

- clear comparator report for both dsRNA and CRISPR
- major systematic ranking errors identified and resolved
- known limitations documented where parity is not intended

## PR3 — Real single-cell and trajectory benchmark expansion

Current state:

- cell-type and trajectory workflows now pass the current proxy benchmark suite
- current benchmark data is still simple and imported-fixture-driven

Objectives:

- validate these workflows on real public datasets with accepted regulators
- reduce the gap between “benchmark pass” and “researcher trust”

Implementation:

- select public benchmark datasets in at least:
  - one human lineage/state transition
  - one immune activation state comparison
  - one plant developmental or cell-state example, if feasible
- build import fixtures and mapping notes
- define accepted regulator lists per benchmark dataset
- add new benchmark scripts or extend current ones to score:
  - top-k regulator recovery
  - state-specific ranking quality
  - stability under subsampling

Validation:

- compare benchmark recovery to literature-accepted regulator sets
- track where current algorithmic shortcuts diverge from expected lineage/state biology

Success criteria:

- at least 2–3 real external datasets incorporated
- measurable regulator-recovery metrics beyond synthetic/proxy fixtures
- documented limitations where current imported-feature abstraction is insufficient

## PR4 — Direct signaling data expansion

Current state:

- signaling benchmark passes via explicit pathway-linked fallback
- current build still has no direct non-TF→TF edge content for the tested human query pattern

Objectives:

- add a biologically stronger direct signaling layer
- reduce dependence on fallback proxy behavior

Implementation:

- identify candidate direct data sources for:
  - ligand/receptor interactions
  - receptor→TF bridge layers
  - curated signaling pathway cascades
- define ingestion model and provenance handling
- add source-aware confidence fields so direct edges remain distinguishable from pathway-proxy results

Validation:

- rerun signaling benchmark with direct-content cases
- add direct-vs-fallback coverage stats

Success criteria:

- direct signaling content exists for at least one major species
- signaling benchmark can pass on direct-edge cases, not only fallback mode
- UI/API clearly distinguish direct evidence from proxy evidence

## PR5 — TF/pathway activity benchmark expansion

Current state:

- TP53 benchmark family is now fixed and passing
- pathway activity currently has a narrow literal benchmark family

Objectives:

- broaden benchmark coverage to reduce overfitting to one success case

Implementation:

- add curated activity cases for:
  - MYC
  - NFkB / RELA
  - STAT1 / interferon response
  - HIF1A / hypoxia
  - at least one plant stress/hormone pathway family
- score top-1 / top-5 / top-10 recovery across cases
- compare `ulm` vs `wmean` across the expanded set

Validation:

- summarize per-family and per-method recovery
- look for families where one scoring mode is consistently worse

Success criteria:

- expanded activity benchmark family covers multiple regulator classes
- no obvious method collapse outside the TP53 case

## PR6 — Species-specific biological gold standards

Current state:

- tomato and petunia gold-standard reports exist
- broader species-specific validation depth is uneven

Objectives:

- improve confidence in plant and non-model usage scenarios

Implementation:

- extend curated gold-standard edge sets where feasible for:
  - Arabidopsis
  - tomato
  - petunia
  - one additional species if data quality supports it
- add phenotype-linked benchmark sets where possible, not just edge-level validation

Validation:

- regenerate per-species quality reports
- track recall, specificity, precision, and unresolved symbol burden

Success criteria:

- expanded gold-standard coverage
- lower unresolved-symbol burden
- stronger species-layer documentation for what is validated vs inferred

## PR7 — Release-grade benchmark governance

Current state:

- benchmark generation is implemented
- artifact persistence exists
- long-term governance is still lightweight

Objectives:

- make validation outputs easier to compare across commits and releases

Implementation:

- version benchmark artifact schemas
- add benchmark manifest metadata:
  - commit SHA
  - run date
  - data freshness snapshot
  - benchmark corpus version
- define a release checklist item for validation reruns
- optionally archive benchmark snapshots per release tag

Validation:

- verify artifact manifests are complete and consistent
- verify release-to-release benchmark comparison is straightforward

Success criteria:

- benchmark artifacts are traceable and comparable across releases
- release readiness reviews can rely on stable validation evidence

## Recommended execution order

1. PR1 — dashboard/artifact hardening
2. PR3 — real single-cell and trajectory benchmark expansion
3. PR4 — direct signaling data expansion
4. PR2 — external comparator studies for dsRNA and CRISPR
5. PR5 — TF/pathway activity benchmark expansion
6. PR6 — species-specific biological gold standards
7. PR7 — benchmark governance

Rationale:

- PR1 improves trust in the existing outputs immediately
- PR3 and PR4 address the areas that only recently moved from weak to passing and still have the thinnest biological benchmark depth
- PR2 is high-value but can proceed after the workflow-level weak spots are better grounded

## Suggested milestone framing

If this work is implemented as post-release sprints:

- Sprint PR-1: dashboard/schema hardening
- Sprint PR-2: real cell-type benchmark ingestion
- Sprint PR-3: real trajectory benchmark ingestion
- Sprint PR-4: signaling data ingestion and direct-edge benchmark
- Sprint PR-5: dsRNA comparator study
- Sprint PR-6: CRISPR comparator study
- Sprint PR-7: activity benchmark expansion
- Sprint PR-8: species gold-standard expansion
- Sprint PR-9: benchmark governance and release snapshot tooling

## Decision

For the current release, no additional validation work in this plan is release-blocking.

This document should be treated as the starting roadmap for the next hardening cycle after release.
