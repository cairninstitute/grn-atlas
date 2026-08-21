# GRN Atlas Validation Summary

Date: Friday, August 21, 2026

This document records the completion status of the validation roadmap execution in this checkout, the validation artifacts that were generated, and the remaining method-hardening gaps.

Related artifacts:

- roadmap: `docs/validation_roadmap_2026-08-21.md`
- initial execution log: `docs/validation_run_summary_2026-08-21.md`
- suite summary: `backend/data/validation_runs/latest_summary.json`
- suite markdown: `backend/data/validation_runs/latest_summary.md`

## What was implemented

The previously missing roadmap validation scripts were added under `backend/scripts/`:

- `validation_common.py`
- `run_validation_suite.py`
- `benchmark_tf_activity.py`
- `benchmark_pathway_activity.py`
- `benchmark_omics_import.py`
- `benchmark_celltype_regulation.py`
- `benchmark_chromatin_support.py`
- `benchmark_trajectory_workflows.py`
- `benchmark_rnai_design.py`
- `benchmark_crispr_design.py`
- `benchmark_perturbation_calibration.py`
- `benchmark_signaling_to_tf.py`
- `benchmark_transferability.py`
- `benchmark_workflow_packaging.py`

The Makefile now includes:

- `make validate-suite`

All benchmark outputs are saved to:

- `backend/data/validation_runs/`

## What was executed

The full suite was run on Friday, August 21, 2026:

- legacy biological validation
  - `backend/scripts/validate_regulation_quality.py`
  - `backend/scripts/validate_network_statistics.py`
  - `backend/scripts/benchmark_beeline.py`
- milestone benchmark suite
  - all 12 new `benchmark_*.py` scripts

Aggregate result:

- suite execution status: `pass`
- scripts executed: `15`
- benchmark JSON outputs written: `12`

Important distinction:

- `suite_status: pass` means every validation script executed successfully.
- it does **not** mean every biological benchmark passed.

## Refreshed legacy validation results

### Gold-standard edge quality

Petunia (`backend/data/quality_report_petunia.json`):

- recall: `93.75%` (30/32 resolved positives)
- specificity: `100%`
- precision: `100%`

Tomato (`backend/data/quality_report_tomato.json`):

- recall: `84.21%` (32/38 positives)
- specificity: `100%`
- precision: `100%`

### Independent edge benchmark

`backend/data/beeline_benchmark_report.json`

Arabidopsis vs DAP-seq:

- AUROC: `0.8801`
- AUPRC: `0.6990`
- precision@100: `0.9000`

Human DoRothEA vs TRRUST:

- AUROC: `1.0000`
- AUPRC: `1.0000`
- precision@100: `1.0000`

### Population-level network validation

`backend/data/network_validation_report.md`

Headline summary:

| Species | Edges | Coherence (σ) | Multi-evidence z | Motif enrichment |
|---|---:|---:|---:|---:|
| arabidopsis | 919,449 | 1.71 | 0.28 | — |
| tomato | 248,288 | 35.17 | 2.36 | 38.55x |
| petunia | 236,727 | 30.25 | 2.08 | 29.53x |
| human | 17,946 | 6.82 | -2.24 | — |
| mouse | 17,692 | — | 0 | — |
| rice | 16,933 | — | 0 | 27.99x |
| potato | 11,409 | — | 0 | 3.33x |
| pepper | 2,212 | — | 0 | 28.5x |

## Milestone validation matrix

The roadmap is complete in the sense that all planned benchmark scripts now exist and were executed. Biological validation quality is mixed by milestone.

| Milestone | Area | Validation status | Notes |
|---|---|---|---|
| M1 | omics import foundation | pass | Clean import, mixed-overlap warnings, repeated-import consistency all passed |
| M2a | pathway activity | pass | Literal p53/DNA-damage case passed; synthetic member-enrichment case passed |
| M2b | TF activity | fail | Literal TP53 recovery failed for both `ulm` and `wmean`; synthetic self-consistency passed |
| M3 | cell-type workflows | partial | upstream recovery and contrast output passed; direct celltype-regulation benchmark did not recover TP53 |
| M4 | chromatin layer | pass | import, peak listing, and cis-support retrieval all passed |
| M5 | trajectory workflows | partial | contrast/activity surfaces execute, but TP53-like benchmark recovery is weak |
| M6 | RNAi / dsRNA | pass | screen, single-gene design, and isoform coverage all passed |
| M7 | CRISPR heuristics | pass | off-target scanning, invalid-length rejection, strategy comparison passed |
| M8 | perturbation calibration | pass | import, concordance comparison, calibration listing passed |
| M9 | signaling → TF | partial | surface works, but current biological content is sparse (`0` non-TF→TF edges in tested human layer) |
| M10 | living validation dashboard | partial | underlying benchmark/status artifacts exist and refresh cleanly, but no dedicated dashboard snapshot/schema benchmark was added yet |
| M11 | transferability / onboarding | pass | transfer-risk, family-rescue, and onboarding readiness all executed successfully |
| M12 | workflow packaging | pass | packaged workflows and study packet/report generation all passed |

Summary count across the 12 milestone benchmark files:

- pass: `8`
- partial: `3`
- fail: `1`

## Main findings

### 1. The strongest validated areas

These areas now have both functioning surfaces and passing benchmark coverage in this checkout:

- import and dataset plumbing
- chromatin import/query/cis-support
- dsRNA screening and design
- CRISPR heuristic design surfaces
- perturbation observation import and concordance comparison
- transferability/onboarding surfaces
- packaged workflows and collaborator-facing report surfaces

### 2. The main method weakness is TF activity

This is the clearest negative result in the suite.

`benchmark_tf_activity.py` shows:

- human TP53-like signature recovery failed under `ulm`
- human TP53-like signature recovery failed under `wmean`
- synthetic self-consistency cases still pass

Interpretation:

- the TF activity implementation is internally coherent enough to recover synthetic seeded regulons
- but it is not yet biologically reliable on a simple literal TP53 perturbation-style sanity case

That makes M2 TF activity the highest-priority method-hardening target.

### 3. Cell-type and trajectory surfaces are useful but not yet biologically hardened

The cell-type and trajectory layers are no longer stubs. They run and return structured results. But the current validation shows they are not yet strong enough to claim robust biological recovery.

Observed issues:

- `celltype/regulation` did not recover TP53 from a TP53-like imported context
- trajectory driver/activity cases produced output but weak recovery of the expected regulator

Interpretation:

- these layers are presently better described as workflow-enabling analysis surfaces than as fully validated biological inference modules

### 4. Signaling is structurally present but biologically sparse

The signaling benchmark is partial for a different reason:

- the surface executes
- a trace call returns cascades
- but the tested human atlas currently has `0` non-TF→TF edges meeting the benchmark query

Interpretation:

- this is primarily a data-layer sparsity issue, not an HTTP/API failure

## Remaining gaps

### High-priority gaps

1. TF activity method hardening

- improve literal perturbation recovery
- benchmark additional known TF perturbation cases beyond TP53
- calibrate regulon-size thresholds and weighting behavior

2. Cell-type biological validation

- benchmark against real public lineage/state datasets
- separate true cluster-specific logic from current “expressed feature set” behavior

3. Trajectory biological validation

- test with real pseudotime or developmental progression datasets
- validate driver recovery against accepted lineage regulators

### Medium-priority gaps

4. M10 dashboard-specific validation

- add schema checks for benchmark JSON inputs
- add rendering/snapshot checks for the validation dashboard
- verify missing-artifact handling directly at the UI component layer

5. Signaling content expansion

- add or ingest real ligand/receptor or receptor→TF bridge data
- then rerun a biologically meaningful signaling benchmark instead of a surface-only smoke case

6. External comparator validation for CRISPR and dsRNA

Current CRISPR and dsRNA validation is useful, but it is still mainly internal/heuristic.

Still missing:

- CRISPR comparison against CRISPOR/CHOPCHOP-like outputs
- dsRNA comparison against specialized RNAi design tools

## Roadmap completion status

Status as of Friday, August 21, 2026:

- benchmark implementation roadmap: complete
- benchmark execution roadmap: complete
- saved run summaries: complete
- final validation summary document: complete

What is not complete is biological hardening of every method. The remaining weak areas are now identified with concrete benchmark evidence rather than assumption.

## Recommended next actions

1. prioritize M2 TF activity fixes first
2. then harden M3 cell-type workflows
3. then harden M5 trajectory workflows
4. treat M9 signaling as a data-acquisition/content-expansion problem
5. add dedicated M10 dashboard tests once UI-level validation is back in scope
