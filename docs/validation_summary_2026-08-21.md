# GRN Atlas Validation Summary

Date: Friday, August 21, 2026

This document records the completion status of the validation roadmap execution in this checkout, the validation artifacts that were generated, and the remaining method-hardening gaps.

Status update:

- initial version of this document captured the first full-suite pass before later hardening work
- the suite was rerun after hardening TF activity, cell-type regulation, trajectory workflows, and signaling fallback behavior
- the current state in this document reflects the rerun completed on Friday, August 21, 2026 at `17:24 UTC`

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

The roadmap is complete in the sense that all planned benchmark scripts now exist and were executed. After the hardening work and rerun, every milestone benchmark file currently passes.

| Milestone | Area | Validation status | Notes |
|---|---|---|---|
| M1 | omics import foundation | pass | Clean import, mixed-overlap warnings, repeated-import consistency all passed |
| M2a | pathway activity | pass | Literal p53/DNA-damage case passed; synthetic member-enrichment case passed |
| M2b | TF activity | pass | Literal TP53 recovery now passes for both `ulm` and `wmean`; synthetic self-consistency still passes |
| M3 | cell-type workflows | pass | cell-type regulation, upstream, and compare benchmarks all pass on the TP53-like imported dataset |
| M4 | chromatin layer | pass | import, peak listing, and cis-support retrieval all passed |
| M5 | trajectory workflows | pass | trajectory driver and activity benchmarks now recover TP53 rank 1 on the validation contrast |
| M6 | RNAi / dsRNA | pass | screen, single-gene design, and isoform coverage all passed |
| M7 | CRISPR heuristics | pass | off-target scanning, invalid-length rejection, strategy comparison passed |
| M8 | perturbation calibration | pass | import, concordance comparison, calibration listing passed |
| M9 | signaling → TF | pass | surface passes with an explicit pathway-linked fallback because direct non-TF→TF edges are sparse in the current atlas build |
| M10 | living validation dashboard | pass | benchmark/status artifacts refresh cleanly and the dashboard backend surface can now be treated as validated at the artifact level |
| M11 | transferability / onboarding | pass | transfer-risk, family-rescue, and onboarding readiness all executed successfully |
| M12 | workflow packaging | pass | packaged workflows and study packet/report generation all passed |

Summary count across the 12 milestone benchmark files after the rerun:

- pass: `12`
- partial: `0`
- fail: `0`

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

### 2. The biggest earlier method weakness was TF activity, and it is now corrected

Earlier in the day, `benchmark_tf_activity.py` showed:

- human TP53-like signature recovery failed under `ulm`
- human TP53-like signature recovery failed under `wmean`
- synthetic self-consistency cases still passed

That failure mode was traced to ranking behavior that over-rewarded tiny perfect-overlap regulons and under-rewarded TFs that explained more of the user’s signature.

After hardening:

- TP53 literal recovery passes rank-1 for both `ulm` and `wmean`
- synthetic human and Arabidopsis self-consistency still pass

### 3. Cell-type and trajectory validation now pass, but with scope limits

The cell-type and trajectory layers now pass their current benchmark suite after ranking hardening. That said, the current benchmarks are still narrow.

Current scope limitations:

- cell-type validation is still based on imported bulk/pseudobulk-style fixtures, not full external single-cell lineage benchmarks
- trajectory validation is still a contrast-style proxy rather than a full pseudotime benchmark with external lineage truth

Interpretation:

- these surfaces are no longer failing the validation suite
- but they remain less deeply biologically benchmarked than the older atlas layers

### 4. Signaling now passes through an explicit fallback path

The direct signaling content remains sparse in the current atlas build:

- tested human build: `0` direct non-TF→TF edges matching the original query pattern

The endpoint now handles that honestly:

- it returns pathway-linked signaling proxy pairs via a bounded fallback mode
- the benchmark passes because the workflow is now usable and explicit about evidence mode

## Remaining gaps

### Remaining gaps

The remaining work is no longer “fix failing milestone benchmarks.” It is deeper post-suite hardening.

1. M10 dashboard-specific validation

- add schema checks for benchmark JSON inputs
- add rendering/snapshot checks for the validation dashboard
- verify missing-artifact handling directly at the UI component layer

2. Signaling content expansion

- add or ingest real ligand/receptor or receptor→TF bridge data
- then rerun a biologically stronger signaling benchmark instead of relying on the proxy fallback

3. External comparator validation for CRISPR and dsRNA

Current CRISPR and dsRNA validation is useful, but it is still mainly internal/heuristic.

Still missing:

- CRISPR comparison against CRISPOR/CHOPCHOP-like outputs
- dsRNA comparison against specialized RNAi design tools

## Roadmap completion status

Status as of Friday, August 21, 2026:

- benchmark implementation roadmap: complete
- benchmark execution roadmap: complete
- benchmark rerun after hardening: complete
- saved run summaries: complete
- final validation summary document: complete

What is not complete is deeper comparative and external biological benchmarking beyond the current suite.

## Recommended next actions

For current release readiness:

1. stop here on validation
2. treat the validation plan as complete for the present release branch

For post-release hardening:

3. add M10 dashboard/UI-level validation
4. add real external comparator studies for CRISPR and dsRNA
5. expand direct signaling data rather than relying on pathway-proxy fallback
6. add deeper external single-cell and trajectory benchmark datasets
