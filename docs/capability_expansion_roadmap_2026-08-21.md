# GRN Atlas Capability Expansion Roadmap

Date: August 21, 2026

Purpose: convert the current capability-gap assessment into a concrete implementation roadmap for making GRN Atlas more useful to researchers, especially relative to specialized regulatory, perturbation, and multi-omic tools.

Status baseline:

- Current GRN Atlas strength: multi-species regulatory atlas, evidence-aware researcher workflows, perturbation planning, dsRNA workflows, cross-species reasoning, validation/handoff outputs.
- Current main gap: limited real support for cell-state-specific, chromatin-aware, perturbation-grounded GRN analysis compared with tools such as SCENIC+, CellOracle, ArchR, decoupler, and Inferelator.

Guiding principles:

1. Preserve GRN Atlas as a workflow-first research system rather than a loose collection of methods.
2. Prioritize capabilities that materially change experiment planning quality.
3. Prefer layered additions that reuse the existing atlas, evidence, workflow, and validation structure.
4. Add strong validation and provenance alongside every new analytical surface.

## Roadmap summary

| Milestone | Theme | Research value | Difficulty | Depends on |
|---|---|---:|---:|---|
| M1 | Standardized omics import foundation | High | Medium | none |
| M2 | TF activity scoring layer | High | Medium | M1 |
| M3 | Cell-type / single-cell regulatory workflows | Very high | High | M1, M2 |
| M4 | Enhancer / chromatin regulatory layer | Very high | High | M1 |
| M5 | Trajectory and state-transition workflows | High | High | M3 |
| M6 | Stronger plant RNAi engine | Very high | Medium | none |
| M7 | Stronger CRISPR design engine | High | High | M4 for best version |
| M8 | Perturbation evidence ingestion and calibration | Very high | High | M2, M3, M5 |
| M9 | Intercellular signaling → TF workflows | Medium-high | High | M2, M3 |
| M10 | Living validation / benchmark dashboard | High | Medium | M2–M8 partial |
| M11 | Non-model species transfer and onboarding hardening | High | Medium | M4, M6 |
| M12 | Researcher-facing workflow packaging | High | Medium | M1–M11 incremental |

## Milestone detail

## M1. Standardized omics import foundation

Goal: make GRN Atlas accept the data structures researchers actually have, rather than only atlas-native inputs.

Scope:

- Add AnnData import support for scRNA-seq and pseudobulk summaries.
- Add sparse matrix + metadata import pathway.
- Add explicit sample/cluster/state metadata normalization.
- Extend current dataset import beyond gene-list/CSV mapping into structured omics import.
- Add export helpers for round-tripping to notebook ecosystems.

Likely deliverables:

- `grn-omics-import`
- `grn-anndata-import`
- import manifest format with provenance and schema checks
- backend staging tables for imported matrices, clusters, states, contrasts
- UI import wizard for omics datasets

Validation:

- fixture AnnData imports for at least 3 public datasets
- schema validation tests for missing metadata, duplicated features, mixed species
- reproducible import report artifact

Success criteria:

- a researcher can import a standard single-cell or pseudobulk dataset without hand-editing code
- imported datasets can be used by downstream TF activity and cell-state workflows

## M2. TF activity scoring layer

Goal: add a robust activity-inference layer similar in practical value to decoupler/DoRothEA-style workflows, but atlas-native.

Scope:

- infer TF activity from expression using signed regulons
- support bulk, pseudobulk, and single-cell cluster/state summaries
- support pathway activity alongside TF activity
- keep resource provenance explicit: atlas regulons vs imported prior resources

Likely deliverables:

- `grn-tf-activity`
- `grn-pathway-activity`
- support for signed and weighted regulons
- activity comparison across contrasts and tissues
- rank + effect-size + confidence output

Validation:

- benchmark against known TF perturbation datasets
- compare atlas regulon scoring versus external prior sets where available
- regression tests for score stability across normalization options

Success criteria:

- researchers can ask “which TFs are active in this state/contrast?” and get a quantitative answer
- outputs integrate naturally with existing enrichment, upstream, and candidate-triage workflows

## M3. Cell-type / single-cell regulatory workflows

Goal: convert the current readiness-only single-cell surface into real analysis functionality.

Scope:

- cell-type-specific regulons
- cluster/state-specific upstream regulator analysis
- differential regulon activity between cell states
- candidate ranking constrained to a chosen cell type
- cell-state-specific evidence boundary reporting

Likely deliverables:

- upgrade `grn-celltype-regulation`
- `grn-celltype-upstream`
- `grn-celltype-regulon`
- `grn-celltype-hypothesis-compare`
- UI views for cell-state explorer and state-specific candidate ranking

Validation:

- reference datasets with known lineage regulators
- reproducibility tests across resampling / pseudobulk strategies
- comparison to published expected regulators in exemplar datasets

Success criteria:

- researchers can ask “which regulators drive this cell state?” and get state-resolved answers
- outputs differ meaningfully by cell type rather than echoing the global atlas

## M4. Enhancer / chromatin regulatory layer

Goal: add real cis-regulatory evidence beyond promoter-only reasoning.

Scope:

- peak-to-gene linkage ingestion
- enhancer-to-target support objects
- motif-in-peak evidence
- chromatin-backed regulator-to-target support scoring
- exportable region-centered evidence

Likely deliverables:

- `grn-peak-gene-linkage`
- `grn-enhancer-network`
- `grn-cis-support-audit`
- region-aware export enhancements
- UI track/evidence pane for enhancer-linked support

Validation:

- import and reproduce at least one public scATAC / multiome linkage dataset
- consistency tests between promoter and enhancer support
- region overlap / coordinate accuracy tests

Success criteria:

- researchers can see whether a claimed TF→target edge has enhancer or chromatin support
- promoter-edit prioritization becomes chromatin-aware instead of promoter-window-only

## M5. Trajectory and state-transition workflows

Goal: move from static state comparisons to transition-aware regulatory analysis.

Scope:

- pseudotime / trajectory metadata support
- regulators of state transitions
- contrast “early vs late” or branch-specific regulatory programs
- transition-aware activity scoring
- explainers for predicted trajectory shifts

Likely deliverables:

- upgrade `grn-trajectory-regulation`
- `grn-transition-drivers`
- `grn-pseudotime-activity`
- `grn-branch-compare`

Validation:

- benchmark on public developmental datasets with accepted lineage drivers
- branch reproducibility under subsampling / pseudotime perturbation
- compare trajectory outputs against static cluster-only outputs

Success criteria:

- researchers can ask “what drives this transition?” rather than only “what differs between these groups?”

## M6. Stronger plant RNAi engine

Goal: make dsRNA design competitive with specialized plant RNAi tools while preserving atlas workflow integration.

Scope:

- isoform-aware design
- richer off-target prediction
- accessibility/efficacy heuristics
- siRNA-pool quality metrics
- improved construct ranking for phenotype-oriented use

Likely deliverables:

- upgrade `grn-dsrna`
- upgrade `grn-dsrna-screen`
- optional transcriptome-wide off-target scanning mode
- efficacy/risk summary object
- better comparison outputs for candidate tradeoffs

Validation:

- compare outputs against pssRNAit / si-Fi-like expectations on benchmark genes
- regression tests for specificity, window stability, and phenotype-target ranking
- performance tests on large candidate panels

Success criteria:

- the best-ranked dsRNA candidates are not only specific, but also more likely to be experimentally useful
- phenotype-oriented RNAi planning becomes a true strength area for GRN Atlas

## M7. Stronger CRISPR design engine

Goal: move from heuristic sequence helpers to practical editing-design support.

Scope:

- genome-aware off-target scanning
- exon and isoform targeting modes
- CRISPRa/CRISPRi/base-edit/prime-edit presets where feasible
- assay-ready exports
- tie editing design to regulatory-site prioritization

Likely deliverables:

- upgrade `grn-crispr-design`
- `grn-guide-offtarget-audit`
- `grn-edit-strategy-compare`
- primer/validation integration

Validation:

- benchmark guide ranking against known standards
- coordinate/off-target correctness tests
- species availability matrix for editing modes

Success criteria:

- researchers can use GRN Atlas for meaningful editing strategy comparison, not only rough guide suggestion

## M8. Perturbation evidence ingestion and calibration

Goal: tie predictions to observed perturbation evidence and reduce purely correlative behavior.

Scope:

- ingest CRISPR screen / Perturb-seq / knockdown result tables
- compare predicted downstream effects against observed effects
- calibrate perturbation confidence by species/context
- capture disagreement explicitly

Likely deliverables:

- `grn-perturbation-import`
- `grn-prediction-vs-observation`
- perturbation calibration reports
- confidence adjustment layer for perturbation outputs

Validation:

- holdout benchmarks on public perturbation datasets
- calibration plots and error summaries
- consistency checks between predicted sign and observed sign

Success criteria:

- GRN Atlas can say not only “what it predicts” but also “how often similar predictions were right”

## M9. Intercellular signaling to TF workflows

Goal: extend from intracellular GRNs to tissue-context regulatory reasoning.

Scope:

- ligand-receptor knowledge ingestion
- receptor-to-TF propagation
- cell-type-to-cell-type signaling hypotheses
- communication-aware upstream analysis

Likely deliverables:

- `grn-ligand-receptor`
- `grn-signaling-to-tf`
- `grn-cellcell-regulation`

Validation:

- benchmark on canonical signaling datasets
- compare propagated TF hypotheses to known response programs

Success criteria:

- researchers can ask which upstream signals might explain a state-specific TF program

## M10. Living validation / benchmark dashboard

Goal: make trust and coverage visible, current, and measurable.

Scope:

- benchmark dashboard across species, layers, and tasks
- confidence calibration summaries
- coverage maps for capabilities
- dataset/version drift tracking

Likely deliverables:

- benchmark JSON + HTML artifacts
- UI validation dashboard
- per-skill and per-layer quality summaries
- release-ready validation snapshots

Validation:

- artifact correctness tests
- scheduled rebuild checks
- provenance-to-benchmark linkage tests

Success criteria:

- users and collaborators can see what is validated, where, and with what evidence

## M11. Non-model species transfer and onboarding hardening

Goal: improve real usefulness in sparse-data plant settings.

Scope:

- better cross-species transfer scoring
- family-level rescue with calibrated confidence
- species onboarding automation
- orthology uncertainty propagation

Likely deliverables:

- upgrade `grn-transferability`
- upgrade `grn-species-onboarding-plan`
- `grn-family-rescue`
- transfer-risk summaries

Validation:

- cross-species recovery benchmarks for known pathways
- manual review on non-model species case studies

Success criteria:

- non-model species workflows become more explicit, more transparent, and more reliable

## M12. Researcher-facing workflow packaging

Goal: ensure the new analytical depth remains usable.

Scope:

- upgrade workflow-first UI to expose new capabilities coherently
- add opinionated experiment design wizards
- add import → activity → regulator → perturbation → design → report paths
- keep advanced panels available without forcing them into primary workflows

Likely deliverables:

- new workflow entry modes
- richer artifacts and result comparison views
- dataset/session state model for imported studies
- release-grade screenshots and docs

Validation:

- end-to-end E2E tests on representative research questions
- usability walkthroughs on at least 5 realistic workflows

Success criteria:

- new depth does not increase UI confusion
- common workflows become shorter, not longer

## Recommended implementation phases

## Phase 1: highest immediate research value

Milestones:

- M1 omics import foundation
- M2 TF activity scoring
- M6 stronger plant RNAi engine

Why:

- these directly improve day-to-day researcher utility
- they fit the current product identity
- they unlock downstream milestones

## Phase 2: biggest strategic gap closure

Milestones:

- M3 cell-type workflows
- M4 enhancer/chromatin layer
- M5 trajectory workflows

Why:

- this closes the largest gap versus SCENIC+, CellOracle, ArchR, and Inferelator

## Phase 3: experiment-facing causal platform

Milestones:

- M7 stronger CRISPR design
- M8 perturbation calibration
- M9 signaling-to-TF workflows

Why:

- this moves GRN Atlas from a strong atlas into a stronger causal experiment planning platform

## Phase 4: trust, transfer, packaging

Milestones:

- M10 living validation dashboard
- M11 non-model species hardening
- M12 workflow packaging

Why:

- these make the new capabilities credible and broadly usable

## Cross-cutting engineering requirements

These should be treated as non-optional for all milestones:

1. Provenance
   - every imported or inferred layer must declare source, version, date, and method

2. Capability boundaries
   - every new skill must report unsupported species, missing layers, and uncertainty clearly

3. Reproducibility
   - every milestone should include deterministic fixtures, benchmark snapshots, and exportable reports

4. Interoperability
   - prefer standard formats: TSV, JSON, AnnData-compatible outputs, documented API responses

5. Validation
   - do not add a major biology-facing feature without an explicit benchmark or correctness check

## Suggested execution order inside the repo

1. Build M1 and M2 first.
2. In parallel, deepen M6 because it is already a product strength.
3. Use M1/M2 as the base for M3.
4. Build M4 before the more ambitious version of M7.
5. Build M8 only after M2/M3/M5 can generate structured perturbation predictions worth calibrating.
6. Keep M10 running continuously as soon as enough new benchmarks exist.

## What success looks like after this roadmap

If the roadmap succeeds, GRN Atlas should be able to do all of the following in a way that is genuinely competitive:

- import a researcher’s bulk or single-cell dataset
- infer state-specific TF and pathway activity
- connect expression changes to network, motif, enhancer, and orthology evidence
- rank intervention targets with explicit uncertainty
- compare RNAi and CRISPR intervention strategies with better design fidelity
- incorporate observed perturbation results to calibrate predictions
- support non-model plant workflows with clearer transfer logic
- produce collaborator-ready outputs without forcing notebook-only usage

That would move GRN Atlas from a strong multi-species atlas with workflow scaffolding into a stronger causal regulatory research platform.

## Gap matrix: milestone to repo surface mapping

This matrix maps each milestone to the concrete surfaces that would need to change in GRN Atlas:

- skills: new or upgraded AgentSkills / workflow logic
- backend tables: likely SQLite entities, caches, or staging tables
- API endpoints: likely FastAPI additions or upgrades
- UI surfaces: likely workflow panels, advanced panels, or artifact views

| Milestone | Skills | Backend tables / data objects | API endpoints | UI surfaces |
|---|---|---|---|---|
| M1 omics import foundation | new: `grn-omics-import`, `grn-anndata-import`; upgrade: `grn-dataset-import`, `grn-input-normalization`, `grn-user-gene-set-analysis` | `imported_datasets`, `imported_features`, `imported_cells`, `imported_samples`, `imported_states`, `imported_contrasts`, import manifests, validation reports | `POST /api/v1/import/omics`, `POST /api/v1/import/anndata`, `GET /api/v1/import/{dataset_id}`, `POST /api/v1/import/{dataset_id}/validate` | import wizard, dataset browser, dataset/session context, uploaded-study artifact drawer |
| M2 TF activity scoring layer | new: `grn-tf-activity`, `grn-pathway-activity`; upgrade: `grn-upstream`, `grn-diff-regulation`, `grn-evidence-audit`, `grn-decision-boundary` | `tf_activity_scores`, `pathway_activity_scores`, `activity_runs`, signed regulon cache, prior-resource metadata | `POST /api/v1/activity/tf`, `POST /api/v1/activity/pathway`, `POST /api/v1/activity/compare`, `GET /api/v1/activity/resources` | TF activity panel, pathway activity panel, state/contrast comparison cards, downstream evidence summaries |
| M3 cell-type / single-cell workflows | upgrade: `grn-celltype-regulation`; new: `grn-celltype-upstream`, `grn-celltype-regulon`, `grn-celltype-hypothesis-compare` | `celltype_regulons`, `state_specific_edges`, `cluster_activity`, `state_rankings`, cluster metadata views | `POST /api/v1/celltype/regulation`, `POST /api/v1/celltype/upstream`, `POST /api/v1/celltype/regulon`, `POST /api/v1/celltype/compare` | cell-state explorer, cluster selector, cell-type-specific candidate ranking workflow, single-cell artifact cards |
| M4 enhancer / chromatin regulatory layer | new: `grn-peak-gene-linkage`, `grn-enhancer-network`, `grn-cis-support-audit`; upgrade: `grn-motif`, `grn-variant-effect`, `grn-promoter-edit-prioritization`, `grn-export` | `chromatin_peaks`, `peak_gene_links`, `enhancers`, `enhancer_gene_links`, `peak_motif_hits`, `cis_support_edges`, genome interval indexes | `POST /api/v1/chromatin/peak-gene-linkage`, `POST /api/v1/chromatin/enhancer-network`, `POST /api/v1/chromatin/cis-support`, `GET /api/v1/chromatin/regions/{region}` | chromatin evidence panel, enhancer-linked edge drawer, region browser, promoter/edit workflow upgrade |
| M5 trajectory and state-transition workflows | upgrade: `grn-trajectory-regulation`; new: `grn-transition-drivers`, `grn-pseudotime-activity`, `grn-branch-compare` | `trajectory_models`, `pseudotime_scores`, `branch_activity`, `transition_driver_scores`, imported trajectory metadata | `POST /api/v1/trajectory/regulation`, `POST /api/v1/trajectory/drivers`, `POST /api/v1/trajectory/activity`, `POST /api/v1/trajectory/compare` | trajectory panel, pseudotime compare workflow, branch contrast cards, dynamic artifact views |
| M6 stronger plant RNAi engine | upgrade: `grn-dsrna`, `grn-dsrna-screen`, `grn-phenotype-targeting`, `grn-experiment-prioritization` | `transcript_isoforms`, `dsrna_design_runs`, `sirna_candidates`, `offtarget_hits`, `efficacy_features`, transcriptome search indexes | `POST /api/v1/rnai/design`, `POST /api/v1/rnai/screen`, `POST /api/v1/rnai/analyze`, `POST /api/v1/rnai/compare` | dsRNA panel, multi-gene RNAi screening, candidate comparison, phenotype-first RNAi workflow upgrade |
| M7 stronger CRISPR design engine | upgrade: `grn-crispr-design`, `grn-primer-design`, `grn-promoter-edit-prioritization`; new: `grn-guide-offtarget-audit`, `grn-edit-strategy-compare` | `crispr_guides`, `guide_offtargets`, `editing_modes`, `guide_primer_pairs`, exon/isoform indexes, PAM configuration tables | `POST /api/v1/crispr/design`, `POST /api/v1/crispr/offtargets`, `POST /api/v1/crispr/compare`, `POST /api/v1/crispr/primers` | renamed advanced editing panel, guide comparison table, assay design workflow, edit-strategy comparison view |
| M8 perturbation evidence ingestion and calibration | new: `grn-perturbation-import`, `grn-prediction-vs-observation`; upgrade: `grn-perturbation`, `grn-cascade`, `grn-confidence-boundary`, `grn-validation-plan` | `perturbation_datasets`, `observed_perturbations`, `prediction_observation_pairs`, `calibration_curves`, `context_accuracy_stats` | `POST /api/v1/perturbation/import`, `POST /api/v1/perturbation/compare`, `GET /api/v1/perturbation/calibration`, `POST /api/v1/perturbation/validate` | perturbation validation panel, prediction-vs-observation artifacts, confidence calibration badges, experiment planning upgrades |
| M9 intercellular signaling to TF workflows | new: `grn-ligand-receptor`, `grn-signaling-to-tf`, `grn-cellcell-regulation` | `ligands`, `receptors`, `ligand_receptor_pairs`, `signaling_paths`, `cellcell_hypotheses`, prior-knowledge imports | `POST /api/v1/signaling/ligand-receptor`, `POST /api/v1/signaling/to-tf`, `POST /api/v1/signaling/cellcell` | signaling workflow, sender/receiver selector, tissue-context hypothesis cards, intercellular artifact drawer |
| M10 living validation / benchmark dashboard | upgrade: `grn-provenance`, `grn-stats`, `grn-coverage-report`, `grn-evidence-audit`; optionally new: `grn-benchmark-status` | `benchmark_runs`, `benchmark_metrics`, `coverage_snapshots`, `validation_artifacts`, `freshness_history` | `GET /api/v1/benchmark/status`, `GET /api/v1/benchmark/{run_id}`, `GET /api/v1/coverage/history`, `GET /api/v1/validation/dashboard` | validation dashboard, benchmark report surfaces, species/layer quality overview, release snapshot views |
| M11 non-model species transfer and onboarding hardening | upgrade: `grn-transferability`, `grn-species-onboarding-plan`, `grn-orthology`, `grn-phenotype-targeting`; new: `grn-family-rescue` | `orthology_confidence`, `family_rescue_candidates`, `species_onboarding_tasks`, `transfer_scores`, species-specific synonym layers | `POST /api/v1/transferability`, `POST /api/v1/family-rescue`, `GET /api/v1/species/onboarding/{species}`, `POST /api/v1/orthology/transfer-risk` | species onboarding planner, non-model candidate rescue workflow, transfer-risk summaries, phenotype-first species guidance |
| M12 researcher-facing workflow packaging | upgrade: `grn-research-brief`, `grn-validation-plan`, `grn-study-packet`, `grn-study-report`, plus all new milestone workflows | no single new table; depends on artifacts from M1–M11 plus a stronger session/workflow state model | `POST /api/v1/workflows/{workflow_id}/run`, `GET /api/v1/workflows/{workflow_id}`, `POST /api/v1/artifacts/package`, `GET /api/v1/session/{session_id}` | workflow-first workspace overhaul, richer artifact drawer, import-to-report guided flows, reusable session state and handoff pages |

## Existing repo surfaces most likely to absorb this work

These are the most probable code locations that would expand under the roadmap:

- skills:
  - `.agents/skills/`
- backend:
  - `backend/main.py`
  - `backend/scripts/build_db.py`
  - `backend/scripts/species_config.py`
  - new backend scripts for import, scoring, linkage, calibration, and benchmarking
  - new tests under `backend/tests/`
- frontend:
  - `src/components/WorkflowWorkspace.jsx`
  - `src/components/AnalysisView.jsx`
  - `src/components/*Panel.jsx`
  - `src/services/apiService.js`
  - workflow components under `src/components/workflows/`

## Recommended milestone-to-code sequencing

To reduce rework, the repo should probably evolve in this order:

1. Add import/session infrastructure once, then reuse it:
   - M1 first

2. Add reusable scoring layers before building many specialized workflows on top:
   - M2 before M3, M5, M8, M9

3. Deepen existing strengths in parallel where dependencies are lighter:
   - M6 can proceed partly in parallel with M1/M2

4. Add chromatin/regulatory evidence before stronger editing workflows:
   - M4 before the full version of M7

5. Add calibration/benchmark/reporting after enough new predictions exist to measure:
   - M8 and M10 after M2–M7 begin producing richer outputs

6. Keep workflow packaging late enough that the underlying analysis surfaces are real:
   - M12 after the main analytical milestones are stable
