# GRN Atlas

GRN Atlas is an interactive multi-species **gene regulatory network atlas** for researchers
who need to move from a gene or gene set to a defensible next step quickly. It combines
regulatory networks, sequence and binding context, expression, pathways, traits,
cross-species conservation, predicted perturbations, and in-silico **dsRNA / RNAi design**
in one workspace — with predicted and inferred results always labelled separately from
measured data.

React + Cytoscape.js frontend · FastAPI + SQLite backend.

Current species coverage: **human, mouse, arabidopsis, tomato, petunia** (with dahlia
onboarding prepared). Data layers vary by species; see the live coverage matrix at
`GET /api/v1/species`.

GRN Atlas can be used in three ways:

- through the browser UI for interactive network exploration
- through the FastAPI backend for programmatic analysis and reproducible workflows
- through the included AgentSkills.io-compatible skills for LLM-guided single-skill and
  multi-step orchestration

This repository is intended for **academic research, education, and non-commercial
exploration**. If you are evaluating it from a fresh clone, the important detail is that
the repository does **not** ship third-party source data or a prebuilt database. You fetch
the upstream inputs locally, build the SQLite atlas, and then run the UI/API on top of
that local build.

---

## Quick start (a fresh clone)

Prereqs: **Python 3.10+**, **Node 18+**, `git`, network access (for the source fetch).

```bash
git clone <this-repo> grn-atlas && cd grn-atlas

# 1. Backend deps
python3 -m venv venv
venv/bin/pip install -r backend/requirements.txt

# 2. Fetch the source data (this repo does NOT redistribute third-party data), then build the DB
venv/bin/python backend/scripts/fetch_sources.py --tier light   # pulls sources into backend/data/ and bootstraps an intermediate DB on fresh clones
venv/bin/python backend/scripts/build_db.py                      # final rebuild -> backend/data/grn.sqlite3 (gitignored)

# 3. Run the API (http://localhost:8000, docs at /docs)
cd backend && ../venv/bin/python -m uvicorn main:app --port 8000

# 4. In another shell: run the UI (http://localhost:3001, proxies /api to :8000)
npm install && npm run dev
```

Or with the Makefile: `make setup && make fetch && make db`, then `make backend` and
(elsewhere) `make frontend`. To add inferred regulatory edges from expression data:
`make infer` (runs GRNBoost2 + GENIE3, ~15 min), then `make db` again to load them.

> **Data is not committed.** Third-party data (each under its own upstream licence — see
> LICENSE) is fetched from source by `fetch_sources.py`; the ~420 MB SQLite DB is then built
> locally by `build_db.py`. The **core atlas** (genes, interactions, coordinates, orthologs,
> GO, pathways, traits, curated symbols, sequence context) comes from the `core`/`light`
> tiers. The **heavy layers** — expression (kallisto over public RNA-seq) and predicted
> binding (motif scans over multi-GB genomes) — are optional, need kallisto/BLAST+, and take
> much longer; `build_db` loads whatever caches are present, so a clone always yields a
> working atlas and those layers light up once regenerated.
>
> **This `light` build is not the full atlas.** Two core inputs (the measured Arabidopsis
> network + ATRM) are not auto-fetched, and the expression/binding layers are optional and
> tool-heavy. See **[Full data setup, caveats & quality checks](#full-data-setup-caveats--quality-checks)**
> below for the complete, verified setup.

## Tests

```bash
venv/bin/pip install -r backend/requirements-dev.txt
venv/bin/python -m pytest backend -q     # backend: unit + DB-invariant + API-contract
npm run test                             # frontend (vitest)
```

## License

This repository is **source-available for non-commercial use**. Academic research,
education, and personal experimentation are allowed under the terms in
[LICENSE](LICENSE). Commercial use, hosted service use, internal business use, or
redistribution as part of a paid product or service requires separate permission
from CAIRN Institute.

For software citation metadata, see [CITATION.cff](CITATION.cff). For data-source
citations, use the provenance and BibTeX endpoints described below.

Important scope boundaries:

- **Code in this repository** is licensed under the project-level
  source-available non-commercial license in [LICENSE](LICENSE).
- **Fetched third-party data** is **not** covered by the repository license. Each
  upstream source keeps its own terms and may impose additional academic-use or
  redistribution restrictions.
- **Contributions** are governed by [CONTRIBUTING.md](CONTRIBUTING.md) and
  [CLA_POLICY.md](CLA_POLICY.md). If you submit code, you must have the right to do
  so and you grant CAIRN Institute the rights needed to maintain and commercialize
  the project.

## Full data setup, caveats & quality checks

The `light` quick-start above gives a working atlas, but **not every layer is fully
automatic.** Here is exactly what each step provides, what needs manual work, and how to
confirm the build is complete.

### What each tier provides

| Tier / step | Command | Provides | Auto? | Needs |
|---|---|---|---|---|
| core | `fetch_sources.py --tier core` | genes, **human** network (TRRUST), coords, orthologs, GO | mostly | network |
| light | `fetch_sources.py --tier light` | + pathways, traits, sequence-context windows, curated UniProt symbols | mostly | network; BLAST+ for petunia symbols |
| manual core | *(see below)* | **measured Arabidopsis network** + its tomato/petunia projection | **no** | manual download |
| heavy | `fetch_expression.py`, `motif_scan.py` | expression + predicted binding | **no** | kallisto / BLAST+, hours, GBs |

`build_db.py` glob-loads whatever caches are present and **skips missing inputs gracefully**
(printing `(skip) …`), so a partial fetch always yields a working — if reduced — atlas.

### ⚠️ Caveats (know these before relying on a fresh clone)

1. **Two core inputs are NOT auto-fetched** — their upstreams are unreliable or need
   reshaping, so `fetch_sources.py` only prints guidance:
   - `backend/data/regulation_arabidopsis.tsv` — the **measured Arabidopsis TF→target
     network**. Without it you lose the Arabidopsis edges **and** the inferred tomato/petunia
     edges projected from them (a large share of the plant networks).
   - `backend/data/atrm_regulations.tsv` — ATRM literature-curated direction labels (refine
     Arabidopsis edge signs). Optional; the atlas works without it.
2. **Heavy layers are optional and slow** — expression (kallisto over dozens of public
   RNA-seq runs = hours) and predicted binding (motif scans over multi-GB genomes). A basic
   clone has neither; the dsRNA/expression/binding features light up once regenerated.
3. **`petunia` curated symbols need BLAST+** (`fetch_curated_symbols.py petunia` homology-maps
   real names). Skipped automatically if BLAST+ isn't on `BLAST_BIN`/PATH.
4. **A full from-scratch fetch has not been certified end-to-end** — it hits several live
   sources; expect occasional retries. Each fetcher is the same one that produced the shipped
   data, and graceful degradation is tested, but plan to spot-check (see quality checks).

### Ensuring the manual core files

- **`regulation_arabidopsis.tsv`** — a tab-separated file with **no header**, one edge per
  line, exactly four columns: `TF_locus  target_locus  activation|repression  confidence`
  (AGI ids, e.g. `AT1G01060`; confidence 0–1). Produce it from PlantRegMap's Arabidopsis
  regulation data (https://plantregmap.gao-lab.org/, TF→target / FunTFBS) reduced to those
  four columns.
- **`atrm_regulations.tsv`** *(optional)* — tab-separated **with a header row**; ≥5 columns
  where col 1 = TF locus, col 2 = target locus, col 5 = direction label `A` / `R` / `D`.
  Source: ATRM (http://atrm.cbi.pku.edu.cn/). Skip if unavailable.

Place both in `backend/data/`, then run `fetch_sources.py --tier light` and `build_db.py` again. The fetch script now bootstraps an intermediate database automatically on fresh clones so DB-dependent fetchers can resolve atlas gene IDs.

### Regenerating the heavy layers (optional)

Install the compute tools once (see **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** for the
kallisto/BLAST+ bootstrap), then per plant species:

```bash
# expression (kallisto index of the species CDS + a curated RNA-seq panel in species_config)
EXPR_SUBSAMPLE=3000000 venv/bin/python backend/scripts/fetch_expression.py petunia
# predicted binding (JASPAR-plant PWM scan over the genome)
venv/bin/python backend/scripts/motif_scan.py petunia /path/to/genome.fa
venv/bin/python backend/scripts/load_seqctx.py petunia         # load motifs+hits into the DB
```

Both are driven by `backend/scripts/species_config.py` (assembly, URLs, RNA-seq panel).
To add a species see **[docs/ONBOARDING_SPECIES.md](docs/ONBOARDING_SPECIES.md)**.

### Quality checks — confirm the build is complete & correct

```bash
# 1. Referential-integrity + sanity invariants over the built DB
venv/bin/python -m pytest backend/tests/test_db_invariants.py -q

# 2. Per-species layer coverage (network / orthologs / binding / expression / pathways / traits)
curl -s localhost:8000/api/v1/species | python3 -m json.tool

# 3. Source-currency audit (loaded vs latest upstream version)
curl -s localhost:8000/api/v1/provenance/freshness | python3 -m json.tool
```

A **complete** build (all tiers + manual core + heavy layers) should report roughly:
`~50,800` genes · human `~4,859` edges · arabidopsis `~91,844` edges · tomato measured
`12,719` + inferred `~197,618`. `build_db.py`'s own summary prints these counts — compare
them, and use `/api/v1/species` to see which layers are populated vs empty. If a layer is
unexpectedly empty, its source file wasn't fetched (check the `(skip)` lines from `build_db`).

## Analysis capabilities

The **Analysis** tab (frontend) and matching agent skills provide advanced network analysis:

| Feature | Skill | Description |
|---|---|---|
| Regulon extraction | `grn-regulon` | BFS expansion of a TF's direct + indirect targets at configurable depth |
| Regulon comparison | `grn-regulon-compare` | Overlap, Jaccard similarity, and hypergeometric significance between two TFs' regulons |
| Upstream regulators | `grn-upstream` | Given a gene set, rank TFs by enrichment (hypergeometric + BH FDR) |
| Network patterns | `grn-network-patterns` | Detect autoregulation, feed-forward loops, and bi-fan motifs |
| Centrality metrics | `grn-centrality` | Degree (in/out/total), betweenness, closeness, eigenvector via igraph |
| Motif / promoter analysis | `grn-motif` | Query JASPAR TF binding motif hits in gene promoters; cross-reference with regulatory edges |
| Module / community detection | `grn-module` | Detect co-regulated gene modules via louvain, leiden, infomap, or label propagation |
| Differential regulation | `grn-diff-regulation` | Compare TF regulatory activity between tissue groups using expression + edge concordance |
| Network inference | `grn-infer` | GRNBoost2 / GENIE3 inferred regulatory edges from expression data; compare with curated network |

### Network inference (GRNBoost2 / GENIE3)

The `grn-infer` skill exposes regulatory edges predicted from expression data using two
complementary algorithms:

- **GRNBoost2** — gradient boosting regression per target gene (~2 min/species)
- **GENIE3** — random forest regression per target gene (~4 min/species)

Both use the existing RNA-seq expression matrices (arabidopsis 18 samples, tomato 20,
petunia 29) with known TFs as candidate regulators. Edges are precomputed by
`backend/scripts/infer_grn.py`, stored in the `inferred_edges` SQLite table (100K edges
per method per species, 600K total), and queryable by gene, direction, method, and
importance threshold. The `--compare-curated` flag cross-references inferred edges against
the curated network to identify which predictions have independent experimental support.

**Caveat:** With only 18–29 samples, these predictions are noisy. Feature importance scores
range 0–0.73 (not the unbounded scores from dask-based GRNBoost2). All inferred edges are
clearly labeled `Inferred:GRNBoost2` or `Inferred:GENIE3` and never mixed with curated
edges without distinction.

### Frontend panels

All current skills are exposed in the React frontend. The **Analysis** tab organizes them into
grouped sections:

| Section | Panels |
|---|---|
| **Regulon & Upstream** | Regulon Extraction, Regulon Comparison, Upstream Regulators |
| **Network Structure** | Network Patterns, Centrality Metrics, Module Detection, Motif Query |
| **Inference & Comparison** | Inferred Edges, Differential Regulation |
| **Export** | Edge Export (JSON/TSV with genomic context) |
| **Workflows** | 7 multi-skill chained panels (see below) |

Cross-panel integration: extract a regulon → one click sends the gene set to upstream
regulator analysis.

### Multi-skill workflows

Chained API call panels that combine two skills in sequence:

| Workflow | Chain | What it does |
|---|---|---|
| Inferred → Enrichment | `grn-infer` → `grn-enrichment` | Predict TF targets via GRNBoost2/GENIE3, then GO-enrich the target set |
| Module → Motif | `grn-module` → `grn-motif` | Detect gene communities, click one to run TF motif enrichment on its promoters |
| Regulon → Differential | `grn-regulon` → `grn-diff-regulation` | Extract a TF's regulon, then compare its activity across tissue conditions |
| Inferred → Validation | `grn-infer` → curated cross-ref | Predict regulatory edges, then show which have independent curated support (validation rate) |
| Research Brief | `grn-candidate-triage` → `grn-experiment-prioritization` → `grn-evidence-audit` / `grn-coverage-report` | Build a structured next-step brief for candidate selection, evidence review, and experiment design |
| Validation Plan | `grn-research-brief` → `grn-validation-plan` | Convert a brief into a go/no-go checklist with decision gates, blockers, and success criteria |
| Study Packet | `grn-research-brief` → `grn-validation-plan` → `grn-study-packet` | Assemble a collaborator handoff packet with execution notes, provenance, and citation-ready context |
| Study Report | `grn-study-packet` → `grn-study-report` | Turn the structured packet into a collaborator-facing markdown report with summary, validation status, and citations |

All listed skills also work as **AgentSkills.io** agent tools in `.agents/skills/`, supporting both
direct (SQLite) and HTTP (`--http URL`) modes.

### Complete skill inventory

The repository currently contains **47 documented skills**:

- **46 callable analysis/workflow skills** listed below
- **1 overview/router skill**: `grn-atlas-overview`

| # | Skill | Description |
|---|---|---|
| 1 | `grn-gene-search` | Fuzzy gene search by name, symbol, or ID |
| 2 | `grn-gene-info` | Detailed gene information (symbol, type, TF status, synonyms) |
| 3 | `grn-network` | Get regulators and/or targets of a gene with confidence scores |
| 4 | `grn-pathfinding` | Find regulatory paths between two genes |
| 5 | `grn-enrichment` | GO, pathway, and trait enrichment for gene sets |
| 6 | `grn-expression` | Per-sample TPM expression profiles (arabidopsis, tomato, petunia) |
| 7 | `grn-coexpression` | Find co-expressed gene partners across RNA-seq panels |
| 8 | `grn-perturbation` | Predict downstream effects of gene knockouts |
| 9 | `grn-subgraph` | Extract regulatory subgraph among a set of genes |
| 10 | `grn-orthology` | Find orthologs and compare regulatory edges across species |
| 11 | `grn-conservation` | Score conservation of regulatory edges between species |
| 12 | `grn-cascade` | Model regulatory cascades from fold-change perturbations |
| 13 | `grn-regulon` | BFS expansion of a TF's regulatory targets at configurable depth |
| 14 | `grn-regulon-compare` | Compare two TF regulons (overlap, Jaccard, hypergeometric) |
| 15 | `grn-upstream` | Identify upstream regulators enriched for a gene set |
| 16 | `grn-stats` | Global database statistics (genes, edges, species coverage) |
| 17 | `grn-species` | Species manifest with per-species layer availability |
| 18 | `grn-provenance` | Data source versions, DOIs, and freshness audit |
| 19 | `grn-citations` | BibTeX citations for all integrated data sources |
| 20 | `grn-centrality` | Degree, betweenness, closeness, eigenvector centrality |
| 21 | `grn-dsrna` | Design dsRNA constructs for RNAi gene silencing |
| 22 | `grn-dsrna-screen` | Screen multiple genes for dsRNA designability |
| 23 | `grn-network-patterns` | Detect autoregulation, feed-forward loops, bi-fan motifs |
| 24 | `grn-export` | Export regulatory edges with genomic coordinates (JSON/TSV) |
| 25 | `grn-motif` | Query TF binding motif hits in gene promoters (JASPAR 2024) |
| 26 | `grn-module` | Community detection on regulatory networks (louvain/leiden/infomap) |
| 27 | `grn-diff-regulation` | Differential TF activity between tissue conditions |
| 28 | `grn-infer` | GRNBoost2/GENIE3 inferred regulatory edges from expression data |
| 29 | `grn-evidence-audit` | Audit support for a gene or edge across loaded evidence layers |
| 30 | `grn-coverage-report` | Score whether a species has the right loaded layers for an analysis intent |
| 31 | `grn-candidate-triage` | Rank a candidate gene list for a research intent |
| 32 | `grn-experiment-prioritization` | Recommend next analyses or experiments for selected genes |
| 33 | `grn-confidence-boundary` | State what the atlas supports, does not support, and leaves ambiguous |
| 34 | `grn-transferability` | Assess whether a candidate-level story transfers across species |
| 35 | `grn-minimal-validation` | Compress a validation plan into the smallest defensible next step |
| 36 | `grn-evidence-synthesis` | Build a writing-ready, atlas-grounded evidence summary with PMIDs and citations |
| 37 | `grn-hypothesis-compare` | Compare competing candidate hypotheses and explain the current winner |
| 38 | `grn-research-brief` | Build a structured multi-step research and experiment brief |
| 39 | `grn-validation-plan` | Build an execution-ready validation checklist and decision matrix |
| 40 | `grn-study-packet` | Assemble a shareable collaborator handoff packet with brief, plan, and citations |
| 41 | `grn-study-report` | Turn a study packet into a collaborator-facing narrative report with markdown |
| 42 | `grn-dataset-import` | Parse a user gene list/CSV/TSV, map genes onto the atlas, and report ambiguous or unmapped rows |
| 43 | `grn-user-gene-set-analysis` | Run enrichment, upstream-regulator analysis, candidate triage, and subgraph extraction on a user-provided gene set |
| 44 | `grn-differential-expression` | Compare atlas tissue groups or import a precomputed DEG table to identify genes with the largest expression changes |
| 45 | `grn-experiment-optimizer` | Re-rank follow-up experiments using budget, timeline, and allowed assay constraints instead of only scientific priority |
| 46 | `grn-literature-review` | Retrieve recent external literature for a gene, edge, pathway, or phenotype and classify papers as support, contradiction, or mention |

## Agent skills

```bash
# Direct mode (local SQLite)
venv/bin/python .agents/skills/grn-regulon/scripts/run.py --gene-id TP53 --depth 1

# HTTP mode (against running server)
venv/bin/python .agents/skills/grn-upstream/scripts/run.py --http http://localhost:8000 \
  --gene-ids "BAX,BCL2,CDKN1A,MDM2"

# Run all skill tests
venv/bin/python .agents/skills/_test_all_skills.py       # 294 direct tests
venv/bin/python .agents/skills/_test_all_skills_http.py  # 59 HTTP tests (server must be running)
venv/bin/python .agents/skills/_test_integration.py      # 49 integration tests (cross-skill, adversarial, perf, idempotency)
npx playwright test                                       # 22 browser e2e tests (server must be running)
```

## LLM orchestration testing

The skill suite has been tested with an external LLM (Nvidia Nemotron-3 Ultra 550B via
OpenRouter free tier) to validate tool selection and multi-step orchestration:

| Test tier | Cases | Tested | Pass rate | What it tests |
|---|---|---|---|---|
| **Direct (no LLM)** | 294 | 294 | 100% (294/294) | Skill execution, argument handling, output validation against ground truth |
| **HTTP mode** | 59 | 59 | 100% (59/59) | All skills via REST API with running server |
| **Integration** | 49 | 49 | 100% (49/49) | Cross-skill consistency, boundary/adversarial, performance regression, idempotency |
| **E2E (Playwright)** | 22 | 22 | 100% (22/22) | Browser tests: all views, 14 analysis panels, 4 workflow chains, URL state |
| **Single-skill LLM** | 305 | 305 | 92.8% (283/305) | LLM selects the correct tool and extracts correct parameters from natural language |
| **Multi-skill orchestration** | 35 | 35 | 94.3% (33/35) | LLM chains 1–7 skills across multi-step biology and workflow questions |

All **47 documented skills** have repository documentation, and all **46 callable
analysis/workflow skills** plus the `grn-atlas-overview` router skill have LLM-facing
coverage in the current skill suite.
The latest full Nemotron single-skill rerun exercised **305/305** cases with **93.4%**
tool-selection accuracy (**285/305**) and **283/305** full-case passes. Subsequent
targeted prompt/skill/harness fixes improved the previously weak RNAi-screen,
conservation, inferred-edge, and workflow chains; the latest full orchestration rerun
reached **33/35 PASS** on Saturday, August 8, 2026.

Integration tests (`_test_integration.py`) cover four categories:
cross-skill consistency (regulon↔network, search↔info, inferred↔curated, orthology, expression↔coexpression),
boundary/adversarial (SQL injection, unicode, empty inputs, nonexistent species, extreme thresholds),
performance regression (timing gates on all major skills), and idempotency (repeated queries return identical results).

Multi-skill orchestration questions cover patterns like: network intersection, RNAi experiment
pipelines, regulon comparison + enrichment, cross-species conservation, upstream analysis +
validation, cascade modeling, expression-guided network analysis, inferred-edge validation,
candidate ranking, evidence synthesis, collaborator handoff, and full experimental design
workflows. Test harnesses are in `.agents/skills/_test_llm_orchestration.py`,
`_test_llm_single_skill.py`, and `_test_integration.py`.

## Docs
- **[ROADMAP.md](ROADMAP.md)** — living source of truth: capabilities, honest boundaries,
  plan, and a dated iteration log.
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** — run, test, rebuild, compute-dep bootstrap.
- **[docs/ONBOARDING_SPECIES.md](docs/ONBOARDING_SPECIES.md)** — add a new species.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — contribution process, review expectations, and
  contributor rights terms.
- **[CLA_POLICY.md](CLA_POLICY.md)** — contributor license terms that preserve CAIRN
  Institute's productization rights.

## Data provenance & citations
Every integrated source (TRRUST, PlantRegMap, PLAZA, OMA, JASPAR, Plant Reactome, GWAS
Catalog, UniProt, mygene, …) is listed with version + DOI in the machine-readable manifest
at `GET /api/v1/provenance` (BibTeX at `/api/v1/citations.bib`), and a data-currency audit
is at `/api/v1/provenance/freshness`. **Each source keeps its own upstream licence** —
consult the manifest before redistributing derived data.

## Guiding principle
Never present predicted/inferred/curated data as measured. Inferred edges
(`Inferred:Arabidopsis` / `Inferred:Expression`), predicted binding sites (`JASPAR_scan`),
inferred gene labels, and homology-mapped symbols (`UniProt:homology`) are all flagged as
such in the API and UI.
