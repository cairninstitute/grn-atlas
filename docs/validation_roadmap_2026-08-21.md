# GRN Atlas Validation Roadmap

Date: August 21, 2026

Purpose: define a concrete validation and method-hardening plan for the newly implemented GRN Atlas roadmap features, with emphasis on biological validity, comparative method quality, robustness, and workflow usefulness.

This document is not about whether endpoints exist. It is about whether the newly added methods and workflows are trustworthy enough to support real research decisions.

## Validation goals

Every milestone should be evaluated against four questions:

1. Does it execute correctly?
2. Does it recover known biology on trusted benchmarks?
3. Does it behave stably under realistic input variation?
4. Does it improve a researcher’s decision quality or experimental planning quality?

## Validation tiers

## Tier A — API, schema, and regression correctness

Objective:

- verify endpoint contracts
- verify input validation
- prevent regressions in existing behavior

Current status:

- partially in place via backend tests and UI tests

What this tier does not prove:

- biological correctness
- method competitiveness
- calibration quality

## Tier B — biological benchmark validation

Objective:

- test whether the implemented methods recover accepted biology from external reference datasets

Examples:

- does TF activity recover known perturbed TFs?
- do cell-type workflows recover accepted lineage regulators?
- do transfer-risk scores distinguish conserved from non-conserved cases?

## Tier C — comparative method validation

Objective:

- compare GRN Atlas outputs to specialized external tools or accepted reference workflows

Examples:

- GRN Atlas TF activity vs decoupleR / DoRothEA-like expectations
- GRN Atlas dsRNA ranking vs pssRNAit / si-Fi-like behavior
- GRN Atlas CRISPR suggestions vs CHOPCHOP / CRISPOR-like outputs

## Tier D — workflow validation

Objective:

- determine whether the full researcher workflow produces better or faster decisions

Examples:

- does “target → perturbation” select a defensible intervention strategy?
- does “import → activity” guide a researcher to a plausible regulator shortlist?
- does workflow packaging improve handoff quality without hiding uncertainty?

## Milestone-by-milestone validation plan

## M10 — living validation dashboard

Goal:

- validate that the dashboard is a faithful view of current benchmark state, not a decorative report surface

Benchmark inputs:

- existing BEELINE benchmark reports
- network validation reports
- per-species quality reports

Checks:

- counts in dashboard match source artifacts
- dashboard renders missing-data states correctly
- per-species metrics are not silently dropped or mislabelled

Success thresholds:

- 100% consistency between dashboard values and source benchmark files
- no rendering failure when one report is absent

Hardening tasks:

- add schema validation for benchmark JSON files
- add snapshot tests for dashboard rendering

## M2 — TF / pathway activity

Goal:

- validate that TF and pathway activity scoring recovers known regulators and pathways from external perturbation datasets

Benchmark datasets:

- public TF perturbation bulk RNA-seq contrasts
- pathway perturbation contrasts
- pseudobulk contrasts from public single-cell studies

Recommended benchmark families:

- TP53 perturbation
- MYC perturbation
- NFkB pathway stimulation / inhibition
- hormone or stress-response pathways in plants where regulons are known

Metrics:

- top-1, top-5, top-10 recovery of expected TF
- AUROC / AUPRC for known active TF set where available
- pathway rank recovery
- rank stability under normalization variants
- concordance of sign with expected target behavior

Success thresholds:

- expected TF in top-5 for at least 60–70% of curated TF perturbation contrasts
- expected pathway in top-10 for at least 70% of pathway perturbation contrasts
- rank correlation > 0.8 under mild normalization changes

Hardening tasks:

- benchmark `ulm` vs `wmean`
- test regulon-size threshold sensitivity
- report species-by-species performance splits

Recommended scripts:

- `backend/scripts/benchmark_tf_activity.py`
- `backend/scripts/benchmark_pathway_activity.py`

## M1 — omics import foundation

Goal:

- validate that imported datasets map cleanly into atlas workflows and fail transparently when they do not

Benchmark datasets:

- small bulk matrix fixture
- pseudobulk fixture
- single-cell-like cluster summary fixture
- at least one mixed-quality real public dataset

Metrics:

- gene mapping rate
- species-detection correctness
- metadata retention correctness
- import reproducibility
- validation report correctness

Success thresholds:

- >90% mapping on well-formed benchmark datasets with matching species
- clean warnings for low-overlap or mixed-species inputs
- identical results on repeated imports

Hardening tasks:

- messy input stress tests
- duplicate feature handling
- inconsistent sample count handling
- incorrect species label handling

Recommended scripts:

- `backend/scripts/benchmark_omics_import.py`

## M3 — cell-type / single-cell workflows

Goal:

- validate that state-specific workflows recover accepted regulators rather than echoing the global network

Benchmark datasets:

- public single-cell datasets with accepted lineage regulators
- at least one mammalian dataset and one plant dataset if feasible

Candidate benchmark families:

- hematopoiesis
- immune activation state transitions
- plant root or developmental cell-state datasets

Metrics:

- top-k recovery of known cell-state TFs
- differential regulator recovery between known states
- cluster-specific vs global regulator divergence
- stability under pseudobulk and subsampling

Success thresholds:

- accepted lineage/state TFs in top-10 for target clusters in a majority of benchmark states
- cluster-specific results measurably different from global-only results
- subsampling rank stability above pre-defined threshold

Hardening tasks:

- benchmark with and without shared gene set filtering
- evaluate contrast dependence
- measure low-cell-count fragility

Recommended scripts:

- `backend/scripts/benchmark_celltype_regulation.py`

## M4 — chromatin / enhancer layer

Goal:

- validate that imported cis-support improves edge support quality instead of merely storing peak data

Benchmark datasets:

- public peak-to-gene linkage references
- DAP-seq or ChIP-supported locus sets
- multiome linkage examples where possible

Metrics:

- recovery of known linked genes
- motif-consistent enrichment among linked peaks
- edge-support improvement relative to network-only ranking
- coordinate integrity and import correctness

Success thresholds:

- significant enrichment of known regulatory support over random baseline
- chromatin-supported edges rank above unsupported edges in curated test sets

Hardening tasks:

- chromosome naming normalization
- duplicate peak import behavior
- mismatched assembly detection

Recommended scripts:

- `backend/scripts/benchmark_chromatin_support.py`

## M5 — trajectory workflows

Goal:

- validate that trajectory-oriented analysis recovers accepted transition drivers beyond static DEG analysis

Benchmark datasets:

- developmental pseudotime datasets
- differentiation datasets with known branch drivers

Metrics:

- top-k recovery of expected transition TFs
- branch-specific regulator separation
- improvement over static differential analysis baseline
- robustness to pseudotime ordering perturbation

Success thresholds:

- transition-driver recovery better than static DEG-only baseline on benchmark datasets
- stable results under modest perturbation of ordering

Hardening tasks:

- compare early-vs-late simplification against true ordered inputs
- evaluate branch imbalance

Recommended scripts:

- `backend/scripts/benchmark_trajectory_workflows.py`

## M6 — RNAi / dsRNA enhancements

Goal:

- validate that RNAi design and ranking are biologically sensible and directionally consistent with specialized RNAi tools

Benchmark datasets:

- curated plant RNAi targets with known good/bad designs
- petunia, tomato, arabidopsis benchmark genes
- pathway-scale candidate panels

Comparators:

- pssRNAit-like outputs
- si-Fi-like outputs

Metrics:

- off-target ranking agreement
- best-window stability
- specificity agreement
- phenotype-oriented target ranking quality
- transcript/isoform sensitivity

Success thresholds:

- high agreement on obviously specific vs obviously problematic targets
- stable top-window choice under minor transcript changes
- phenotype-target shortlist improves over specificity-only baseline

Hardening tasks:

- incomplete transcriptome stress tests
- isoform ambiguity tests
- non-model species transcript quality checks

Recommended scripts:

- `backend/scripts/benchmark_rnai_design.py`

## M7 — stronger CRISPR design

Goal:

- validate that the current CRISPR layer produces defensible guide and strategy comparisons

Benchmark datasets:

- benchmark genes in human and Arabidopsis
- known guide regions where public comparators agree strongly

Comparators:

- CHOPCHOP-like outputs
- CRISPOR-like outputs

Metrics:

- overlap with accepted guide regions
- off-target burden ranking consistency
- strategy ranking coherence across knockout / CRISPRi / CRISPRa

Success thresholds:

- no gross disagreement with accepted guide regions on benchmark targets
- strategy summaries match known mechanistic expectations

Hardening tasks:

- invalid-length input tests
- species-specific sequence availability checks
- guide ranking sensitivity analysis

Recommended scripts:

- `backend/scripts/benchmark_crispr_design.py`

## M8 — perturbation evidence ingestion and calibration

Goal:

- validate that observed perturbation imports improve trust in predictions and produce meaningful calibration summaries

Benchmark datasets:

- CRISPR knockout result tables
- knockdown response sets
- Perturb-seq summaries where feasible

Metrics:

- sign concordance
- precision / recall on affected genes
- confidence-bin calibration
- species/context performance stratification

Success thresholds:

- monotonic or near-monotonic relationship between confidence and correctness
- useful concordance summaries on at least one external perturbation dataset family

Hardening tasks:

- contradictory replicate handling
- sparse observation handling
- mixed assay-type imports

Recommended scripts:

- `backend/scripts/benchmark_perturbation_calibration.py`

## M9 — signaling → TF workflows

Goal:

- validate that signaling-to-TF traces recover accepted downstream TF programs rather than generic network hubs

Benchmark datasets:

- canonical signaling pathway examples
- pathway-specific receptor-to-TF cases

Candidate benchmark families:

- TNF / NFkB
- TGF-beta / SMAD-associated programs
- plant hormone-response examples

Metrics:

- recovery of known downstream TFs
- false positive rate among high-degree generic regulators
- depth-1 vs depth-2 usefulness

Success thresholds:

- known downstream TFs appear near the top for canonical pathways
- outputs are not dominated by generic central nodes

Hardening tasks:

- penalize hub inflation
- quantify pathway specificity

Recommended scripts:

- `backend/scripts/benchmark_signaling_to_tf.py`

## M11 — species transfer hardening

Goal:

- validate that transfer-risk and family-rescue outputs separate strong transfer cases from weak ones

Benchmark datasets:

- known conserved pathways across species
- known divergent regulatory cases
- non-model plant examples with sparse direct data

Metrics:

- conserved-edge recovery
- false transfer rate
- family-rescue hit quality
- calibration of low / medium / high risk labels

Success thresholds:

- lower predicted transfer risk should correspond to stronger observed conservation
- family rescue should add useful candidates without overwhelming noise

Hardening tasks:

- paralog-rich family tests
- sparse target-species network tests
- orthology-confidence threshold sensitivity

Recommended scripts:

- `backend/scripts/benchmark_transferability.py`

## M12 — workflow packaging

Goal:

- validate that the packaged workflows improve researcher productivity and do not hide important uncertainty

Benchmark inputs:

- realistic research questions
- benchmark gene lists
- imported omics fixtures

Core workflows to test:

- `deg-to-regulators`
- `target-to-perturbation`
- `import-to-activity`

Metrics:

- workflow completion rate
- accuracy of recommended next action versus expert judgment
- number of manual steps reduced
- artifact usefulness for collaborator handoff

Success thresholds:

- workflows consistently produce a plausible next step on benchmark cases
- experts agree that outputs are decision-useful in most cases

Hardening tasks:

- ambiguity handling
- unsupported-species handling
- incomplete-input workflow behavior

Recommended scripts:

- `backend/scripts/benchmark_workflow_packaging.py`

## Validation dataset bundle

Create a reproducible validation dataset bundle with frozen manifests.

Suggested contents:

- 5–10 TF perturbation benchmark contrasts
- 3–5 pathway perturbation contrasts
- 2–3 single-cell or pseudobulk benchmark datasets
- 2 chromatin / linkage benchmark datasets
- 1–2 plant RNAi benchmark panels
- 1–2 CRISPR comparison benchmark panels
- 1–2 cross-species transfer case studies
- 1 signaling benchmark set

Suggested manifest file:

- `backend/data/validation_datasets_manifest.json`

Suggested storage layout:

- `backend/data/validation_runs/`
- `backend/data/validation_inputs/` or fetch scripts + manifest if raw inputs should not be committed

## Standard metrics to report

All benchmark scripts should emit a standard schema when applicable:

- benchmark name
- species
- method
- dataset identifier
- top-k recovery
- AUROC
- AUPRC
- precision@k
- rank correlation / stability
- calibration metrics
- notes on missingness / unsupported layers

## Global success criteria for calling a milestone validated

A milestone should not be called validated unless all of the following are true:

1. API and regression tests pass
2. At least one external biological benchmark family is passed at the defined threshold
3. Failure boundaries are documented
4. Benchmark outputs are reproducible from scripts or fixed manifests

## Recommended execution order

Run validation in this order:

1. M10 validation dashboard consistency
2. M2 TF / pathway activity
3. M6 RNAi / dsRNA
4. M1 omics import
5. M3 cell-type workflows
6. M4 chromatin / enhancer
7. M8 perturbation calibration
8. M5 trajectory workflows
9. M11 species transfer
10. M9 signaling → TF
11. M7 CRISPR
12. M12 workflow packaging

Reason:

- this order validates the highest-value biology-facing layers first
- later workflows depend on earlier surfaces being meaningful

## Concrete implementation tasks for the validation program

Add these scripts and artifacts:

- `backend/scripts/run_validation_suite.py`
- `backend/scripts/benchmark_tf_activity.py`
- `backend/scripts/benchmark_pathway_activity.py`
- `backend/scripts/benchmark_omics_import.py`
- `backend/scripts/benchmark_celltype_regulation.py`
- `backend/scripts/benchmark_chromatin_support.py`
- `backend/scripts/benchmark_trajectory_workflows.py`
- `backend/scripts/benchmark_rnai_design.py`
- `backend/scripts/benchmark_crispr_design.py`
- `backend/scripts/benchmark_perturbation_calibration.py`
- `backend/scripts/benchmark_signaling_to_tf.py`
- `backend/scripts/benchmark_transferability.py`
- `backend/scripts/benchmark_workflow_packaging.py`

Recommended report outputs:

- `backend/data/validation_runs/latest_summary.json`
- `backend/data/validation_runs/latest_summary.md`
- milestone-specific JSON and markdown reports

## Final recommendation

The current repo now contains a broad first-pass implementation of the roadmap. The highest-value next move is to validate these additions in the same explicit, benchmarked style that already exists for the atlas network quality surface.

The goal is not only to improve correctness. The goal is to know, milestone by milestone:

- where GRN Atlas is already strong
- where it is useful but still heuristic
- where it is not yet ready for strong biological claims

That is what will make the roadmap additions credible to researchers.
