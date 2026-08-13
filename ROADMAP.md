# GRN Atlas — Capabilities & Roadmap (living document)

> This is the single, continuously-updated map of what GRN Atlas can do, where it
> falls short, and what we're building next. **Update it every iteration:** when a
> capability ships, move it up; when a gap closes, strike it; append to the
> Iteration Log. The working loop is: _build → test → document here → find gaps →
> plan → repeat._

Last updated: 2026-08-13 · Current broad status: 61 documented skills, GPT-5.4 single-skill matrix 347/347 PASS, GPT-5.4 orchestration matrix 59/59 PASS.

---

## 1. What we can do today (capabilities → problems solved)

### Regulatory structure
- **Who regulates gene X / what does TF Y target** — neighborhood + network view,
  filterable by direction, confidence, evidence source, and measured-vs-inferred;
  PubMed links per edge.
- **Path from A → B** — pathfinding (BFS over signed edges).
- **Master regulators / core circuit** — Organism tab (hub ranking, core-circuit graph).

### Gene-set interpretation
- **Functional theme of a set** — GO enrichment (hypergeometric + BH FDR).
- **Pathway membership of a set** — pathway enrichment (`/api/v1/pathway_enrichment`),
  Plant Reactome (arabidopsis + tomato) and Reactome/WikiPathways via mygene (human);
  same hypergeometric+BH machinery. In the gene-set panel.
- **Phenotype/trait linkage (human)** — GWAS Catalog associations: per-gene traits
  (`/api/v1/traits/{id}`) and trait enrichment for a gene set / regulon
  (`/api/v1/trait_enrichment`). Statistical (SNP→mapped gene→trait), not mechanistic.
  Verified: SP1's targets enrich for Alzheimer's disease (q=0.043) + HDL/lipid traits.
- **Which TFs drive a set** — motif enrichment over the scanned-promoter background,
  now for tomato, petunia, and **arabidopsis** (e.g. AN2 top-enriched in petunia
  flavonoid promoters q=4e-5; BPC1 targets enrich the BPC1 motif in arabidopsis q=1.9e-83).
- **Actionable coordinates** — export of signed edges + confidence + genomic coords
  + promoter windows + predicted binding sites (tomato/petunia).

### Expression & co-expression (all three plant species)
- **Per-tissue expression profile** — `GET /api/v1/expression/{gene_id}`: TPM across a
  species' RNA-seq panel, quantified with kallisto vs PLAZA CDS. Petunia (29 samples,
  floral/pigmentation), tomato (20: leaf/root/stem/flower/bud/fruit/apex/cotyledon),
  arabidopsis (18: shoot/inflorescence/root/seedling). Predicted/shallow (subsampled);
  the endpoint auto-selects by gene species.
- **Predicted co-expression** — `POST /api/v1/coexpression`: Pearson on log2(TPM+1),
  labeled `Inferred:Expression`, undirected (not causal, not measured regulation).
  `tf_only` restricts partners to candidate TF regulators. Shown in the gene detail panel.
- Verified: AN2 peaks in flower/corolla/petal-limb; co-expresses with petal-identity
  genes (PI/AP3); 3 of AN2's 18 network targets are independently co-expressed —
  expression corroborating a subset of projected edges.

### dsRNA / RNAi design (in-silico gene silencing)
- **Design a dsRNA or predict its silencing** — `POST /api/v1/dsrna`: analyze mode (given a
  dsRNA → on-target coverage + ranked off-target genes + specificity, both strands, exact
  siRNA k-mer match) or design mode (given a target gene → most-specific window). Chains
  `silenced_genes` → `/perturb` for the predicted downstream phenotype, and annotates
  off-targets with tissue expression. Predicted, not measured (labelled). `🧬 dsRNA` panel.
  Verified: a designed 250 nt dsRNA vs petunia AN2 → 0 off-targets (specificity 100%),
  230 on-target sites, → predicted anthocyanin-target down-regulation.
- **Batch pathway screen** — `POST /api/v1/dsrna/screen`: rank a gene set / Reactome pathway
  by dsRNA-designability (fewest off-targets in the best window; one transcriptome pass) +
  the combined-silencing predicted effect. Available for petunia, tomato, arabidopsis
  (transcript stores committed); turnkey for any species with `transcripts_<species>.fasta.gz`.

### Perturbation prediction
- **Predict downstream effects of a TF knockout/over-expression** — `POST /api/v1/perturb`
  propagates signs along the network (activation +1 / repression −1 × intervention sign),
  confidence-weighted and depth-damped. Returns predicted up/down/unknown per reachable
  gene with the path. Unsigned edges → "unknown"; inferred routes flagged. Drives the
  Intervention Designer. Verified: AN2 knockout → its anthocyanin targets predicted down.

### Comparative / evolutionary
- **Edge conservation across species** — `/api/v1/conservation` joins orthologs +
  both networks (JAF13→CHS conserved petunia↔tomato; AN2→CHS diverged).
- **Synteny / orthologs** — genome view, ideograms, ribbons.

### Practical / trust
- **Gene identification despite messy annotation** — BLAST regulator ID + synonym search.
- **Cite & reproduce** — provenance manifest + BibTeX + versioned methods in exports.
- **Judge data currency** — freshness audit (`/api/v1/provenance/freshness`): each source's
  loaded version vs the latest available release, with an "update available" badge in the
  Data & citations panel. Re-runnable via `check_source_freshness.py`.
- **Share** — permalinks; exports (PNG/SVG/GraphML/JSON/CSV/TSV); collections.
- **Teach** — student scaffolding (examples, glossary, inferred-edge explainers).

### Species & data
- 5 species: human, mouse, arabidopsis, tomato, petunia.
- Measured edges: TRRUST v2 (human), PlantRegMap FunTFBS (tomato, arabidopsis).
- Inferred edges: Arabidopsis network projected onto tomato/petunia (`Inferred:Arabidopsis`).
- Sequence context: promoter/gene-body windows + JASPAR-scan binding sites (tomato/petunia).
- Orthology/coords: OMA, PLAZA Dicots 4.5, DNA Zoo *P. axillaris* Hi-C.

---

## 2. Honest boundaries (what bounds rigor today)

- **Expression covers the three plant species only, and is shallow** — subsampled panels
  (petunia 29, tomato 20, arabidopsis 18); relative/co-expression signal, not absolute.
  Human/mouse have no expression axis. (Tomato: only atlas genes whose PLAZA CDS version
  matches get expression.)
- **No dynamics** — the cascade/intervention view is a toy, not a quantitative model.
- **Petunia edges are inferred** — hypotheses, not evidence; no measured petunia GRN.
- **No accessibility (ATAC), PPI/complexes, or phenotype/QTL linkage.**
- **Data currency** — PLAZA 4.5 is 2018 (dicots 5.0 now exists, flagged by the freshness
  audit); TRRUST v2 is older. Currency is now *surfaced*; actual re-fetch/rebuild to newer
  releases (and adding species e.g. wheat/cotton) remains future work.

**Guiding principle:** never fabricate scientific data. Inferred/predicted/curated
data must always be labeled distinct from measured (inferred edges, JASPAR_scan
sites, BLAST_curated symbols). New inferred layers inherit this rule.

---

## 3. Expansion plan — items 1–6 (value-ranked)

Numbered by research value. **Execution order differs** (feasibility-first): the
data-free item ships first, then the expression linchpin, then the rest.

| # | Feature | Unlocks | New data needed | Effort |
|---|---------|---------|-----------------|--------|
| 1 | **Expression integration** | condition/tissue-specificity, co-expression, expression-weighted TFBS | RNA-seq atlases | High |
| 2 | **Network inference from expression** (GENIE3/ARACNe-style) | a data-driven petunia network (not just projected) | uses #1 data | High |
| 3 | **Perturbation modeling upgrade** | "predict effect of knocking out AN2" via signed-path propagation | none | Medium |
| 4 | **Base-resolution binding for human/arabidopsis** | motif enrichment + seq context for best-measured species | JASPAR/ReMap ChIP | Medium |
| 5 | **Broader enrichment + trait linkage** | KEGG/MapMan pathways; QTL/GWAS→gene | KEGG, GWAS/QTL | Medium |
| 6 | **Taxonomic scope / freshness** | wheat/cotton homoeologs; refreshed PLAZA/TRRUST | newer releases | Medium |

### Execution sequence (feasibility-first)
1. **#3 perturbation** — no external data; uses existing signed edges. *Start here.*
2. **#1 + #2 expression + inference** — the linchpin; do together (inference consumes
   the loaded expression). Removes the static + petunia-only-inferred ceiling.
3. **#4 base-resolution binding** — extends the strongest existing analysis to human/arabidopsis.
4. **#5 enrichment + trait linkage.**
5. **#6 scope/freshness.**

### Per-item design sketch
- **#3:** replace toy cascade with signed-path propagation over `interactions`
  (sign = activation/repression product along path, with sign-flip on repression;
  damped by confidence & depth). Endpoint `POST /api/v1/perturb` (KO/OE list →
  predicted up/down per reachable gene, with path evidence). Honest labeling:
  output is "predicted direction," qualitative, gated by inferred-edge inclusion.
- **#1:** new `expression(gene_id, species, sample, tpm)` + `samples(...)` tables from
  public RNA-seq (tomato PRJNA980935 / expression atlases; Arabidopsis; petunia if
  available). Endpoints: per-gene expression profile; expression-weighted edge/motif
  views. Cache to committed JSON like other fetchers; runtime stays offline.
- **#2:** `infer_network.py` — GENIE3-style tree importance (or correlation fallback)
  per species from #1's matrix → `Inferred:Expression` edges, labeled distinct from
  both measured and Arabidopsis-projected. Compare against projection in the UI.
- **#4:** extend `motifs`/`motif_hits` + crosswalk to human/arabidopsis using
  JASPAR/ReMap; reuse existing motif-enrichment + seq-context machinery.
- **#5:** `go_annotations`-style tables for KEGG/MapMan; QTL/GWAS→gene mapping table;
  reuse hypergeometric+BH; new "trait" lookup endpoint.
- **#6:** refresh fetchers to current PLAZA/TRRUST; add wheat/cotton with homoeolog
  handling.

---

## 4. Known gaps / backlog (revisit each iteration)
- ~~Perturbation model is a toy~~ ✅ shipped (#3): signed-path propagation, honest unknown/inferred labels.
- ~~Static network — no time/condition axis~~ ✅ shipped (#1) for petunia: 29-sample expression profiles.
- ~~Petunia has no data-derived network~~ ✅ shipped (#2): co-expression inference (`Inferred:Expression`).
  Follow-ups: ✅ expression extended to tomato/arabidopsis. **GENIE3/tree-based directed network is
  NOT viable on available data** — validated at BOTH 29 and 63 samples that tree-importance
  doesn't reliably recover known edges (see log); needs condition/perturbation-rich data (not
  just more tissue replicates) before it's honest to ship.
- ~~Sequence layer absent for arabidopsis~~ ✅ shipped (#4, plant side): TAIR10 JASPAR scan (95k sites).
  Human base-resolution binding (ReMap/JASPAR vertebrate) still pending — larger genome + peak ingest.
- ~~Only GO enrichment~~ ✅ #5 shipped: pathway enrichment (Plant Reactome, plant side) +
  trait linkage (GWAS Catalog, human). Pending: human/mouse pathways (Reactome, needs
  ENSG→symbol map); plant QTL trait data (sparse, no clean gene-mapped source).
- ~~No visibility into stale releases~~ ✅ #6 (freshness half): currency audit surfaces
  staleness (PLAZA 4.5→5.0 flagged). Actual refresh-to-newer + new species (wheat/cotton) still open.
- ~~Older scaffold docs predate recent features~~ ✅ pruned; docs are now README + DEVELOPMENT + ONBOARDING_SPECIES + ROADMAP.

## 5. Iteration Log

## 5A. Sprint 7–11 researcher-skill expansion plan

- **Sprint 7 — Hypothesis comparison**
  - Add a skill to compare two or more candidate genes/mechanisms/gene sets for the
    same research intent.
  - Output: ranked comparison, decisive evidence differences, conflicting signals,
    confidence delta, and a recommended winner with overturn conditions.
  - Validation: unit/API tests plus direct/HTTP skill coverage and one cross-skill
    consistency check against existing triage/brief outputs.

- **Sprint 8 — Confidence boundary / negative-result analysis**
  - Add a skill to state what the atlas can and cannot support for a question.
  - Output: supported claims, unsupported claims, ambiguity sources, missing layers,
    safe interpretations, and concrete data needed to reduce uncertainty.
  - Validation: unit/API tests plus direct/HTTP skill coverage on both strong and weak
    evidence scenarios.

- **Sprint 9 — Cross-species transferability**
  - Add a skill to assess whether a regulatory claim or candidate can be transferred
    from one species to another.
  - Output: transferability score, conserved support, missing assumptions,
    species-specific caveats, and recommended validation steps in the target species.
  - Validation: unit/API tests plus direct/HTTP skill coverage and integration checks
    against orthology/conservation outputs.

- **Sprint 10 — Minimal validation path**
  - Add a skill to convert a candidate and intent into the smallest defensible
    execution path for follow-up.
  - Output: minimal first step, prerequisite checks, blocker list, stop/go gates,
    cheaper alternatives, and escalation path if the first step fails.
  - Validation: unit/API tests plus direct/HTTP skill coverage and consistency with
    validation-plan outputs.

- **Sprint 11 — Evidence synthesis**
  - Add a skill to synthesize atlas-backed evidence into a paper-style summary for a
    gene or gene set without pretending to do external literature retrieval.
  - Output: support summary, contradictory/weak evidence summary, source-backed
    narrative, PMIDs/citations already present in the atlas, and reporting caveats.
  - Validation: unit/API tests plus direct/HTTP skill coverage and consistency with
    evidence-audit/provenance outputs.

- **2026-08-07** — Shipped **research-readiness / evidence audit layer**. Added
  `backend/evidence.py` + `GET /api/v1/evidence/audit` to summarize support for a
  gene or edge across curated interactions, projected/inferred layers, motifs,
  coexpression, pathways, traits, and ortholog context with a confidence label and
  coverage gaps. Added the `grn-evidence-audit` skill plus direct/HTTP harness
  coverage. Also added `backend/context.py` + `GET /api/v1/coverage/report` to
  score species/intents for readiness and recommend next skills from loaded layers.
  This closes a trust gap for researchers asking “how well-supported is this?” or
  “can this species honestly answer my question?” Verified with new unit/API tests
  and harness integration.

## 5B. Sprint 12+ researcher workflow expansion plan

### Objective

Extend GRN Atlas from an atlas-internal analysis system into a broader researcher
workflow system that can answer:

- what does the atlas know?
- what does the latest literature say?
- what does my dataset say?
- what intervention or assay should I run next under real constraints?
- how would a variant, promoter edit, or CRISPR perturbation change the
  regulatory story?

### Wave structure

The next expansion should be built in three waves:

1. **Wave 1 — user-data and decision workflows**
   - `grn-dataset-import`
   - `grn-user-gene-set-analysis`
   - `grn-differential-expression`
   - `grn-experiment-optimizer`
2. **Wave 2 — literature, genetics, and assay expansion**
   - `grn-literature-review`
   - `grn-consensus-ranking`
   - `grn-counterfactual-analysis`
   - `grn-phenotype-to-candidates`
   - `grn-variant-effect`
   - `grn-promoter-edit-prioritization`
   - `grn-crispr-design`
   - `grn-primer-design`
3. **Wave 3 — advanced state/context analysis**
   - `grn-celltype-regulation`
   - `grn-trajectory-regulation`
   - `grn-combinatorial-perturbation`
   - `grn-species-onboarding-plan`

### Major milestones

#### Milestone 1 — user gene-set ingestion and analysis

- Add `backend/importers.py` to parse plain gene lists and CSV/TSV files.
- Add identifier normalization and species guessing over atlas gene IDs/symbols.
- Add `POST /api/v1/datasets/import` to return:
  - parsed rows
  - mapped genes
  - ambiguous/unmapped genes
  - species guess
  - dataset type guess
- Add `POST /api/v1/user/gene-set/analyze` to run:
  - enrichment
  - upstream regulator analysis
  - subgraph extraction
  - candidate triage
  - evidence summaries
- Add skills:
  - `grn-dataset-import`
  - `grn-user-gene-set-analysis`
- Validation:
  - backend unit/API tests
  - direct/HTTP skill tests
  - one integration test chaining import → analysis

#### Milestone 2 — differential-expression workflows

- Add `POST /api/v1/expression/differential`.
- Support:
  - atlas-mode group comparison from named samples/tissues
  - imported DE tables or expression matrices
- Output:
  - ranked DE genes
  - top up/down genes
  - sample-count and confidence warnings
  - recommended downstream skills
- Add skill:
  - `grn-differential-expression`
- Validation:
  - backend unit/API tests
  - direct/HTTP skill coverage
  - integration test: differential → upstream → enrichment

#### Milestone 3 — constraint-aware experiment planning

- Add `POST /api/v1/experiments/optimize`.
- Accept:
  - gene list
  - intent
  - species
  - budget/timeline constraints
  - allowed assay classes
- Output:
  - ranked experiments
  - rationale
  - blockers
  - cheaper/faster alternatives
  - expected information gain proxy
- Add skill:
  - `grn-experiment-optimizer`
- Validation:
  - backend unit/API tests
  - direct/HTTP skill tests
  - integration test against validation-plan/minimal-validation

#### Milestone 4 — literature-grounded external evidence

- Add `backend/literature.py` and external-source adapters.
- Add `GET /api/v1/literature/review`.
- Support:
  - gene
  - edge
  - pathway
  - phenotype/topic queries
- Output:
  - supporting papers
  - contradicting papers
  - latest evidence summary
  - explicit “atlas vs external” boundary
- Add skill:
  - `grn-literature-review`
- Validation:
  - adapter tests with fixtures
  - HTTP/API tests
  - integration test with evidence-audit/evidence-synthesis

#### Milestone 5 — consensus and counterfactual decision support

- Add weighted evidence aggregation across:
  - network support
  - motif support
  - expression/coexpression
  - traits/pathways
  - orthology/conservation
  - literature (if available)
- Add skills:
  - `grn-consensus-ranking`
  - `grn-counterfactual-analysis`
- Validation:
  - consistency tests against candidate-triage/hypothesis-compare
  - LLM routing tests for subtle “why not this gene?” prompts

#### Milestone 6 — variant, promoter-edit, and CRISPR support

- Add sequence-aware variant effect scoring on motif instances.
- Add promoter edit prioritization.
- Add CRISPR guide design and primer design support.
- Add skills:
  - `grn-variant-effect`
  - `grn-promoter-edit-prioritization`
  - `grn-crispr-design`
  - `grn-primer-design`
- Validation:
  - sequence-level unit tests
  - API/skill tests with fixed fixtures
  - integration test with motif/export workflows

#### Milestone 7 — advanced state/context analysis

- Add cell-type / single-cell regulatory analysis when data layers exist.
- Add trajectory/time-series regulatory analysis when data layers exist.
- Add combinatorial perturbation search.
- Add species onboarding planning support.
- Add skills:
  - `grn-celltype-regulation`
  - `grn-trajectory-regulation`
  - `grn-combinatorial-perturbation`
  - `grn-species-onboarding-plan`
- Validation:
  - blocked until the required data layers are present

### Data-bound vs software-bound work

- **Software-bound now**
  - dataset import
  - user gene-set analysis
  - differential expression over current plant panels
  - experiment optimization
  - consensus ranking
  - counterfactual analysis
  - phenotype-to-candidates
- **Needs external API integration**
  - literature review
- **Needs new sequence/tooling layers**
  - variant effect
  - promoter edit prioritization
  - CRISPR design
  - primer design
- **Data-blocked for now**
  - cell-type regulation
  - trajectory regulation

### Validation loop for every milestone

1. Implement backend logic + unit tests.
2. Add API surface + contract tests.
3. Add direct skill wrapper + direct harness coverage.
4. Add HTTP skill wrapper + HTTP harness coverage.
5. Add cross-skill integration coverage.
6. Add/refresh LLM single-skill and orchestration cases.
7. Fix routing/frontmatter ambiguity if the LLM chooses the wrong skill.

### Immediate execution order

1. **Milestone 1** — dataset import + user gene-set analysis
2. **Milestone 2** — differential expression
3. **Milestone 3** — experiment optimizer
4. **Milestone 4** — literature review
5. **Milestone 5** — consensus + counterfactual
6. **Milestone 6** — variant/promoter/CRISPR
7. **Milestone 7** — cell-state / onboarding work

- **2026-08-07** — Shipped **candidate triage + experiment prioritization** on top
  of the evidence/coverage foundation. Added `backend/planning.py`,
  `POST /api/v1/candidates/triage`, and `POST /api/v1/experiments/prioritize`, plus
  the `grn-candidate-triage` and `grn-experiment-prioritization` skills. The atlas
  can now rank gene lists for intents such as network follow-up or RNAi and suggest
  the next plausible analyses/experiments (perturbation, expression context review,
  motif follow-up, dsRNA design, trait follow-up, conservation check) from the
  actually-loaded layers instead of static advice. Validation: backend **125 tests
  green**, HTTP skill harness **65/65**, integration harness **39/39**, plus
  targeted direct-mode checks for the new skills.

- **2026-08-07** — Shipped **research brief / study-design workflow**. Added
  `backend/briefing.py`, `POST /api/v1/research/brief`, and the `grn-research-brief`
  skill to turn a gene list into a structured brief with candidate ranking,
  experiment recommendations, species-readiness context, evidence snapshots,
  explicit risk flags, and an ordered workflow plan. RNAi briefs now lead with
  dsRNA design when transcriptome support is present rather than generic network
  perturbation. This closes the gap between low-level skill outputs and an actual
  researcher-facing next-step plan. Validation: targeted unit/API tests green,
  plus all-skills HTTP + integration regression after backend restart.

- **2026-08-07** — Shipped **validation plan / execution checklist workflow**. Added
  `backend/validation.py`, `POST /api/v1/research/validation-plan`, and the
  `grn-validation-plan` skill to convert a research brief into ranked validation
  tracks, decision gates, blockers, experiment-specific success criteria, failure
  signals, and an ordered execution checklist. RNAi validation plans now start
  with `dsrna_design` when transcriptome support exists, while network-oriented
  plans expose explicit go/no-go gates for weaker or narrower follow-up paths.
  This closes the gap between “what should we do next?” and “what are the concrete
  acceptance criteria before we do it?”.

- **2026-08-07** — Shipped **study packet / collaborator handoff workflow**. Added
  `backend/packet.py`, `POST /api/v1/research/study-packet`, and the
  `grn-study-packet` skill to bundle a research brief, validation plan, execution
  hints, provenance freshness, and citation-ready source context into one
  shareable artifact. The packet surfaces a lead candidate, compact workflow
  metadata, and a collaborator checklist so follow-up work can move from triage
  to execution without re-deriving the rationale. Validation: targeted packet
  unit/API tests, plus direct + HTTP skill and integration regression after
  backend restart.

- **2026-08-07** — Shipped **study report / narrative handoff workflow**. Added
  `backend/reporting.py`, `POST /api/v1/research/study-report`, and the
  `grn-study-report` skill to turn the structured study packet into a readable
  collaborator-facing report with executive summary, candidate table, experiment
  recommendations, validation status, and citation-backed markdown output. This
  closes the last gap between machine-structured planning output and something a
  PI or collaborator can directly read, review, and forward. Validation: targeted
  report unit/API tests, plus direct + HTTP skill and integration regression.

- **2026-08-07** — Shipped **hypothesis comparison workflow**. Added
  `backend/hypothesis.py`, `POST /api/v1/research/hypothesis-compare`, and the
  `grn-hypothesis-compare` skill to compare competing candidate genes for the same
  intent using the existing triage, brief, and experiment-prioritization layers.
  The output now explains the current winner, pairwise decisive factors, ranking
  margins, and explicit overturn conditions instead of only returning independent
  candidate scores. Validation: targeted comparison unit/API tests, plus direct +
  HTTP skill and integration regression.

- **2026-08-07** — Shipped **confidence-boundary workflow**. Added
  `backend/boundary.py`, `POST /api/v1/research/confidence-boundary`, and the
  `grn-confidence-boundary` skill to state what the current atlas state supports,
  does not support, and leaves ambiguous for a candidate set and intent. The
  output now translates evidence support, missing layers, and brief risks into
  explicit unsupported claims, safe interpretations, and concrete data-needed
  notes so researchers can avoid over-claiming from absence-of-evidence cases.
  Validation: targeted boundary unit/API tests, plus direct + HTTP skill and
  integration regression.

- **2026-08-07** — Shipped **cross-species transferability workflow**. Added
  `backend/transferability.py`, `POST /api/v1/research/transferability`, and the
  `grn-transferability` skill to assess whether a candidate-level claim can be
  transferred from the source species into a target species. The output combines
  source confidence, ortholog presence, target-species readiness, explicit caveats,
  and recommended validation steps without pretending that gene-level orthology
  proves exact edge conservation. Validation: targeted transferability unit/API
  tests, plus direct + HTTP skill and integration regression.

- **2026-08-07** — Shipped **minimal validation workflow**. Added
  `backend/minpath.py`, `POST /api/v1/research/minimal-validation`, and the
  `grn-minimal-validation` skill to compress the broader validation plan into the
  smallest defensible next action. The output now highlights the first step,
  prerequisite checks, stop/go gates, blockers, fallback alternatives, and an
  escalation path without forcing the researcher to parse the full validation
  matrix. Validation: targeted minimal-path unit/API tests, plus direct + HTTP
  skill and integration regression.

- **2026-08-07** — Shipped **evidence synthesis workflow**. Added
  `backend/synthesis.py`, `POST /api/v1/research/evidence-synthesis`, and the
  `grn-evidence-synthesis` skill to turn atlas-backed evidence into a writing-ready
  summary with support statements, weak-evidence warnings, stored PMIDs, citation
  bundle context, and reporting caveats. This is intentionally conservative: it
  packages atlas evidence for manuscripts, slides, or collaborator review without
  pretending to do external literature retrieval. Validation: targeted synthesis
  unit/API tests, plus direct + HTTP skill and integration regression.

- **2026-07-28** — **Human base-resolution binding (#45): assessed, deferred with a plan.**
  The useful ReMap-2022 human file (per-TF peaks) is 1.4 GB; the alternative JASPAR-vertebrate
  scan needs the ~3 GB human genome + promoter extraction. Either is a full new pipeline
  (promoter windows from our 1,991 human GRCh38 coords → peak/PWM mapping → motif_hits →
  `_ASSEMBLY_OF['human']='GRCh38'`). Priority-4, and human already has measured TRRUST edges,
  so the marginal value (human motif enrichment) doesn't justify the download/compute now.
  **Concrete plan when prioritised:** stream ReMap nr BED, keep only peaks within ±2 kb of a
  human TSS, aggregate per (TF, target) → predicted binding-site table (tier='ReMap_ChIP',
  measured), reuse the existing motif-enrichment machinery. No data shipped by design.
- **2026-07-28** — **Deepened petunia expression + re-ran the GENIE3 gate — still negative
  (honest result).** Quantified a 63-sample petunia panel (up from 29; all 71 available P.
  axillaris SRA runs, 8 failed to pseudoalign) and re-tested tree-importance recovery of
  known anthocyanin regulation. It did NOT improve: JAF13→CHS stayed decent (~14/616) but
  AN2→CHS (256) and every DFR regulator (112–264) remained noise — no better than at 29
  samples. Conclusion: GENIE3 is **not viable on the available petunia data** (mostly
  tissue/replicate variance across a few studies, not the perturbation diversity GENIE3
  needs; MBW-complex control isn't captured by single-TF importance; shallow subsampled
  quant). Not shipped — pairwise co-expression (#2) remains the honest tool. The clean
  29-sample curated panel is kept (a 63-sample study grab-bag adds batch effects with
  generic labels). Revisit only with condition/perturbation-rich data (e.g. dahlia).

- **2026-07-27** — **PLAZA 5.0 refresh: investigated, deferred (honest call).** Probed
  dicots_05: it has the same species (pax/sly/ath) with the SAME gene IDs (no break) and
  adds `symbol=`/`uniprot=` GFF fields — BUT those symbol fields are **empty for petunia
  and tomato** (0 annotations) and redundant for arabidopsis (already mygene-annotated).
  A full migration means re-running every plant fetcher (coords/synteny/orthology/GO/seqctx)
  + rebuild + re-verifying all plant layers for marginal benefit and real regression risk.
  Deferred as a dedicated future project; the freshness audit (#6) continues to flag 4.5 to
  users transparently. No changes shipped by design.
- **2026-07-27** — **#38 pathway half shipped: human pathway enrichment.**
  `fetch_pathways_animal.py` pulls Reactome + WikiPathways for human/mouse gene symbols
  directly from mygene (no ENSG map needed) → 940 pathways / 11,034 annotations (1,674 human
  genes); `load_pathways_animal.py` loads additively; build_db globs pick them up. Verified:
  a p53 gene set enriches "TP53 network" (q=1.8e-12), DNA-damage-response, p53 pathway.
  Human **base-resolution binding** (JASPAR-vertebrate / ReMap over the ~3 GB human genome)
  is the heavy remaining half — deferred with a note (much larger than the plant scans;
  human already has measured TRRUST edges). +1 API test (106 backend).
- **2026-07-27** — **GENIE3 data-derived petunia network: investigated, deferred (honest
  call).** Ran ExtraTrees tree-importance (GENIE3) over the 29-sample petunia panel and
  checked whether it recovers KNOWN anthocyanin regulation: JAF13→CHS ranked 11/616 TFs
  (encouraging) but AN2→CHS ranked 162 and all three known DFR regulators ranked 233–441
  (noise). **29 shallow samples is too few for a trustworthy directed network**, so we do
  NOT ship one (it would present spurious edges as confident) — the pairwise co-expression
  endpoint (#2) remains the appropriately-humble tool. Prerequisite for revisiting: deepen
  the expression panel (petunia has ~166 public SRA runs; we quantified 29) or use the
  incoming dahlia data. (scikit-learn is now available in the venv for when that lands.)


- **2026-07-27** — Replaced inferred labels with **real curated symbols** where an authoritative
  source exists. `fetch_curated_symbols.py`: tomato from UniProt Swiss-Prot via EnsemblPlants
  Solyc xref (direct); petunia from UniProt *P. hybrida* reviewed proteins tblastn-mapped to
  Peaxi162 loci at ≥90% identity (`UniProt:homology`). `load_curated_symbols.py` + build_db
  durability promote them into `genes.symbol` only where no native symbol existed (AN2 etc.
  preserved), recording a new `symbol_source` column. **155 loci now show real names**
  (PHYB1, ACS2, CCOAOMT1…) instead of loci/inferred; surfaced via `symbol_source` +
  `label_inferred=False`. UniProt added to provenance. +1 API test (94 backend). Arabidopsis
  already mygene-annotated; dahlia will arrive with its own annotation.

- **2026-07-26** — Established this roadmap + baseline (61 backend / 5 frontend green).
  Prior shipped: provenance/citations, cross-species conservation, motif enrichment.
- **2026-07-26** — Shipped **#3 perturbation**: `/api/v1/perturb` signed-path propagation
  replacing the toy cascade; rewired the Intervention Designer to it. +3 API tests
  (64 backend / 5 frontend green). Verified AN2 KO → anthocyanin targets down.
  Next: **#1 + #2** — expression integration + network inference (the linchpin). This
  needs external RNA-seq; first step is a data-availability check + a fetch script
  (cache to committed JSON like other fetchers, runtime stays offline).
- **2026-07-26** — Shipped **#1 + #2 (petunia)**. Reference unblocked via PLAZA pax CDS
  (SGN was down). Built `fetch_petunia_expression.py`: streams subsampled reads for a
  curated 29-sample panel from ENA, kallisto-quantifies to Peaxi162 TPM. New
  `expression.py` + `/api/v1/expression/{id}` (#1) and `/api/v1/coexpression` (#2,
  `Inferred:Expression`, undirected). `ExpressionPanel` in the gene detail view. +7 tests
  (71 backend / 5 frontend). Verified: AN2 pigmented-tissue-specific; co-expresses PI/AP3;
  corroborates 3/18 projected AN2 targets.
- **2026-07-26** — Shipped **#4 (plant side)**: Arabidopsis base-resolution TF binding.
  Reused the plant seqctx/scan machinery — PLAZA ath GFF → TAIR10 promoter windows;
  JASPAR-plant PWM scan (symbol-mapped, 346 TFs) → 95,132 predicted sites; targeted DB
  loader (no full rebuild); enabled arabidopsis in `_ASSEMBLY_OF` so motif enrichment +
  sequence-context now work for it. +1 DB-invariant test (72 backend). Verified: BPC1
  targets enrich BPC1 motif (q=1.9e-83), paralogs BPC5/6 co-enrich.
  Next: **human** base-resolution binding (ReMap/JASPAR vertebrate), then **#5**
  (KEGG/MapMan + trait linkage); also extend expression to tomato/arabidopsis.
- **2026-07-26** — Shipped **#5 (pathway half, plant side)**: Reactome pathway enrichment.
  `fetch_pathways.py` (Plant Reactome → arabidopsis + tomato, version-tolerant tomato match,
  523 pathways / 8,108 annotations) + `load_pathways.py` (targeted) + build_db durability
  (schema + glob). `POST /api/v1/pathway_enrichment` mirrors GO enrichment (hypergeometric+BH);
  gene-set panel gains a Reactome section; Plant Reactome added to provenance/citations.
  +2 API tests (74 backend). Verified: a metabolism gene set enriches Homoserine/Lysine
  biosynthesis (q=0.012).
- **2026-07-26** — Finished **#5** with **trait linkage (human, GWAS Catalog)**:
  `fetch_traits.py` matches GWAS MAPPED_GENE symbols to atlas human IDs → 108,485
  associations (1,977 genes, 21,391 traits); `load_traits.py` + build_db durability.
  `GET /api/v1/traits/{id}` + `POST /api/v1/trait_enrichment` (hypergeometric+BH); gene-set
  panel gains a GWAS trait section; GWAS Catalog added to provenance. +3 API tests (77 backend).
  Verified: SP1 targets enrich Alzheimer's (q=0.043) + HDL/lipid traits.
  **1–6 core plan now complete.** Remaining follow-ups: #6 freshness/scope; human
  base-resolution binding + human/mouse pathways (ENSG→symbol map); extend expression
  to tomato/arabidopsis; upgrade co-expression to tree-based (GENIE3).
- **2026-07-26** — Shipped **#6 (freshness half)**: data-currency audit.
  `check_source_freshness.py` live-probes each source's latest release (PLAZA dicots,
  Reactome) and writes `source_freshness.json`; `provenance.freshness()` +
  `GET /api/v1/provenance/freshness`; Data & citations panel shows an "update available"
  badge. +1 API test (78 backend). Verified: PLAZA correctly flagged stale (4.5 vs 5.0);
  sentinel-versioned sources (GWAS "latest", Plant Reactome "current") correctly read as
  current. **All of 1–6 now have a shipped increment.** Deeper #6 (re-fetch to newer
  releases + rebuild; add wheat/cotton) remains future work, now visible via the audit.
- **2026-07-26** — Backlog: **extended expression + co-expression to tomato**. Generalized
  `expression.get_matrix(species)` + endpoints auto-select the matrix by gene species (petunia
  tests unchanged). `fetch_tomato_expression.py` reuses the petunia ENA/kallisto helpers over a
  curated 20-sample tissue panel vs PLAZA sly CDS (Solyc IDs join the atlas directly) →
  `expression_tomato.json.gz` (34,725 genes). +1 API test (79 backend). Verified: a leaf-marker
  gene (leaf 48k vs root 52 TPM) co-expresses r≥0.93 with a coherent leaf/photosynthesis module.
  Next backlog options: arabidopsis expression; tree-based co-expression (GENIE3); human
  binding/pathways (ENSG→symbol map).
- **2026-07-26** — Backlog: **arabidopsis expression** (completes the plant expression stack).
  `fetch_arabidopsis_expression.py` (18-sample panel: vegetative shoot / inflorescence / root
  / seedling) vs PLAZA ath CDS → `expression_arabidopsis.json.gz` (27,655 genes). No backend
  changes needed — the multi-species machinery handled it. Verified: floral organ-identity
  genes AP3/AG/AP1 are inflorescence-specific (0 TPM in vegetative shoot); AP3 co-expresses
  with MYB21 + floral genes. **All three plant species now have expression + binding + pathways.**
- **2026-07-26** — Shipped **Dahlia-onboarding prep** (real data incoming from Alex/Zach;
  see [memory] grn-atlas-dahlia-collaboration): (1) `species_config.py` central per-species
  registry (with a `dahlia` placeholder); (2) **trait linkage generalized to any species** —
  `ingest_trait_table.py` loads any gene→trait TSV keyed to atlas ids (verified end-to-end on
  a non-human species), and the `/trait_enrichment` note is now dynamic; (3) `GET /api/v1/species`
  capability matrix (network/orthologs/binding/expression/pathways/traits per species) — the
  onboarding-readiness view; (4) `docs/ONBOARDING_SPECIES.md` runbook. +2 API tests (80 backend).
  When Dahlia data lands: add its `species_config` entry + genome/CDS/orthologs, run the
  fetchers, and `ingest_trait_table.py` for Zach's GWAS. Optional follow-up: surface `/species`
  in the UI; fold the near-duplicate seqctx/scan scripts into fully generic config-driven ones.
- **2026-07-27** — Shipped **generic ingestion pipeline + cleanup**. Collapsed the 8
  per-species scripts into 4 config-driven ones off `species_config.py`: `fetch_seqctx.py`
  (PLAZA-identity), `motif_scan.py` (PWM core + scan), `fetch_expression.py` (ENA/kallisto),
  `load_seqctx.py`. Config now carries assembly/URLs/promoter/chrom_norm/scan_edge_sql/
  expr panels per species (tomato seqctx stays bespoke — SGN ITAG lift-over). Verified
  faithful by regeneration+diff: arabidopsis seqctx & motif_hits **byte-identical**, all 3
  expression matrices **identical**, petunia seqctx a +4-gene superset (current DB).
  Cleanup: removed dead unimported `backend/app/` scaffold; standardized tomato motif caches
  to `_tomato` suffix; repointed `test_science.py` to the generic modules. 80 backend / 5
  frontend green. Adding Dahlia is now: config entry + drop-in refs + run the generic scripts.
- **2026-07-27** — Shipped **dsRNA / RNAi design + off-target analysis** (for spraying dsRNA
  on petunia/dahlia). New `rnai.py` (pure: dice→siRNA k-mers both strands, transcriptome
  scan, specificity, design-window search) + committed `transcripts_petunia.fasta.gz` store;
  `POST /api/v1/dsrna` (analyze + design), chaining silenced genes → `/perturb` and
  annotating off-targets with expression; `🧬 dsRNA` frontend panel. +9 tests (6 unit,
  3 API) → 89 backend / 5 frontend. Verified: designed dsRNA vs AN2 is fully specific
  (0 off-targets) and predicts anthocyanin-target knockdown. Dahlia-ready (drop in its
  transcript store) — polyploid homeolog off-targets will surface once its transcriptome lands.
- **2026-07-27** — Extended dsRNA to **tomato + arabidopsis** (committed transcript stores;
  verified a tomato design is fully specific) and added **batch pathway screening**
  (`/api/v1/dsrna/screen` + `rnai.screen`, one transcriptome pass, ranked by designability
  + combined effect) with a screen mode in the 🧬 panel. +2 tests → 91 backend / 5 frontend.
  Verified: petunia anthocyanin set (AN2/JAF13/AN1) all designable; silencing all → 14 down.
