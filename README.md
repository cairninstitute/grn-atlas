# GRN Atlas

GRN Atlas is an interactive multi-species **gene regulatory network atlas** for researchers
who need to move from a gene or gene set to a defensible next step quickly. It combines
regulatory networks, sequence and binding context, expression, pathways, traits,
cross-species conservation, predicted perturbations, and in-silico **dsRNA / RNAi design**
in one workspace — with predicted and inferred results always labelled separately from
measured data.

React + Cytoscape.js frontend · FastAPI + SQLite backend.

Current species coverage: **human, mouse, arabidopsis, tomato, petunia, pepper, potato** (with dahlia
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

Or with the Makefile: `make setup && make fetch && make db && make tissue-weights`, then
`make backend` and (elsewhere) `make frontend`. To add inferred regulatory edges from
expression data: `make infer` (runs GRNBoost2 + GENIE3, ~15 min), then `make db` again to
load them. After building: `make validate` (network validation) and `make benchmark`
(AUROC/AUPRC benchmarks).

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
| core | `fetch_sources.py --tier core` | genes, **human** networks (TRRUST + DoRothEA), coords, orthologs, GO, DAP-seq binding, gene lists | mostly | network |
| light | `fetch_sources.py --tier light` | + pathways, traits, PlantRegMap regulation (tomato/petunia/potato/tobacco/rice), curated symbols, tobacco BLAST orthologs | mostly | network; BLAST+ for petunia symbols + tobacco orthologs |
| manual core | *(see below)* | **measured Arabidopsis network** + ATRM direction labels → Arabidopsis multi-evidence + tomato/petunia/pepper/rice projection | **no** | manual download |
| heavy | `fetch_expression.py`, `motif_scan.py` | expression + predicted binding | **no** | kallisto / BLAST+, hours, GBs |
| tissue-weights | `make tissue-weights` | per-tissue coexpression weights for edges (petunia, tomato, arabidopsis) | yes | built DB + expression data |
| validate | `make validate` | gold-standard recall/specificity + population-level statistical validation | yes | built DB |
| benchmark | `make benchmark` | BEELINE-style AUROC/AUPRC against independent ground truth | yes | built DB |

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
`~142,000` genes · `~1,470,000` interactions · human `~18,000` edges (TRRUST + DoRothEA) ·
mouse `~18,000` edges (TRRUST + DoRothEA) · arabidopsis `~919,000` edges (PlantRegMap +
DAP-seq) · tomato `~248,000` · petunia `~237,000` · rice `~17,000` (Arabidopsis projection) ·
pepper `~2,200` · potato `~11,400`. Tissue coexpression: `~4.18M` weight rows across petunia,
tomato, arabidopsis. `build_db.py`'s own summary prints these counts — compare them, and use
`/api/v1/species` to see which layers are populated vs empty. If a layer is unexpectedly
empty, its source file wasn't fetched (check the `(skip)` lines from `build_db`).

### Network validation

After building, run `make validate` (or the two scripts directly) to produce quality reports:

```bash
# Gold-standard spot-check: recall, specificity, precision against 94 literature-curated edges
venv/bin/python backend/scripts/validate_regulation_quality.py

# Population-level statistical validation across ALL edges (5 tests per species)
venv/bin/python backend/scripts/validate_network_statistics.py
```

The population-level tests assess the full network (not just 94 gold-standard edges) using
orthogonal data types:

1. **Regulon GO coherence** — do a TF's targets share GO terms more than random gene sets?
2. **Permutation test** — is the network-wide coherence significant vs shuffled TF-target
   assignments? (effect size in sigma, p-value)
3. **Multi-evidence quality** — do edges from 2+ independent sources score higher than
   single-source edges? (Mann-Whitney z)
4. **Expression coherence** — do interaction-table edges appear in GRNBoost2/GENIE3
   coexpression more than random pairs?
5. **Motif enrichment** — do Arabidopsis orthologs of inferred targets have the TF's binding
   motif in their promoters more than non-targets?

Results are written to `backend/data/network_validation_report.md` and per-species JSON files.
The gold-standard reports go to `backend/data/quality_report_{species}.json`.

#### Species gene and edge coverage (August 2026)

| Species | Atlas genes | Genome genes | Gene coverage | Edges | TFs | Targets | Multi-evidence | Sources |
|---------|----------:|------------:|--------------:|------:|----:|--------:|---------------:|---------|
| Tomato | 19,256 | 34,075 | 56.5% | 241,828 | 849 | 17,521 | 10,458 | PlantRegMap, Inferred:Arabidopsis, Inferred:Potato, Inferred:Tobacco, Literature |
| Petunia | 14,843 | 32,928 | 45.1% | 231,438 | 691 | 14,556 | 13,041 | PlantRegMap, Inferred:Arabidopsis, Inferred:Potato, Inferred:Tobacco, Literature |
| Arabidopsis | 17,705 | 27,655 | 64.0% | 91,850 | 766 | 17,535 | 1,431 | PlantRegMap, ATRM |
| Mouse | 29,192 | 21,926 | 100%+ | 17,692 | 820 | 5,569 | 409 | TRRUST, DoRothEA |
| Human | 20,659 | 20,596 | 100% | 17,946 | 694 | 5,581 | 2,030 | TRRUST, DoRothEA |
| Potato | 18,374 | 39,028 | 47.1% | 11,409 | 252 | 4,080 | 0 | PlantRegMap |
| Pepper | 2,351 | 34,899 | 6.7% | 2,203 | 99 | 973 | 0 | Inferred:Arabidopsis |

Genome gene counts: NCBI/Ensembl protein-coding annotations (TAIR10, ITAG4.1, Peaxi162, PGSC v4.03, Pepper.v.1.55).
Mouse >100% because the mygene.info gene list includes some non-protein-coding entries.

#### Edge quality validation

**Gold-standard (94 literature-curated edges):**

| Species | Recall | Specificity | Precision | FP rate |
|---------|-------:|----------:|----------:|--------:|
| Petunia | 93.8% (30/32) | 100% (11/11) | 100% | 3.5% |
| Tomato  | 84.2% (32/38) | 100% (12/12) | 100% | 2.0% |

**Population-level (all edges, 5 orthogonal tests):**

| Species | Edges | Coherence (σ) | Multi-ev. z | Motif enrichment |
|---------|------:|-------------:|----------:|----------------:|
| Tomato | 241,828 | 37.7 | 1.74 | 32.4× |
| Petunia | 231,438 | 30.2 | 3.08 | 25.8× |
| Arabidopsis | 91,850 | 7.7 | 30.8 | — |
| Human | 17,946 | 7.8 | −4.3 | — |
| Mouse | 17,692 | — | — | — |
| Pepper | 2,203 | — | — | 18.3× |
| Potato | 11,409 | — | — | 2.8× |

Key: **Coherence (σ)** = permutation test effect size (higher = more significant);
**Multi-ev. z** = Mann-Whitney z comparing multi-source vs single-source edges;
**Motif enrichment** = fold enrichment of TF binding motifs in inferred target promoters.
"—" = insufficient data for that test (no GO annotations, no expression, or no motif data).

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

The repository currently contains **100 documented GRN Atlas skills**:

- **99 callable analysis/workflow skills**
- **1 overview/router skill**: `grn-atlas-overview`

The full live inventory, with every skill name and current description, is maintained in:

- [docs/SKILL_INVENTORY.md](docs/SKILL_INVENTORY.md)

That inventory is the canonical skill list for the current repo state and supersedes older partial lists from earlier release phases.

## Agent skills

```bash
# Direct mode (local SQLite)
venv/bin/python .agents/skills/grn-regulon/scripts/run.py --gene-id TP53 --depth 1

# HTTP mode (against running server)
venv/bin/python .agents/skills/grn-upstream/scripts/run.py --http http://localhost:8000 \
  --gene-ids "BAX,BCL2,CDKN1A,MDM2"

# Run legacy skill harnesses
venv/bin/python .agents/skills/_test_all_skills.py       # 319 direct tests across 41 skills
venv/bin/python .agents/skills/_test_all_skills_http.py  # 83 HTTP tests across 41 skills (server must be running)
venv/bin/python .agents/skills/_test_integration.py      # 49 integration tests (cross-skill, adversarial, perf, idempotency)
npx playwright test                                       # 22 browser e2e tests (server must be running)

# Current LLM routing/orchestration matrices
venv/bin/python .agents/skills/_test_llm_single_matrix.py --provider openai --model gpt-5.4
venv/bin/python .agents/skills/_test_llm_orchestration_matrix.py --provider openai --model gpt-5.4
```

## LLM orchestration testing

The skill suite has been tested with external LLMs to validate tool selection and multi-step
orchestration. The current repo status as of **Saturday, August 22, 2026** is:

| Test tier | Cases | Tested | Pass rate | What it tests |
|---|---|---|---|---|
| **Direct skill harness** | 319 | 319 | 100% (319/319) | Local skill execution, argument handling, output validation against ground truth for the legacy 41-skill harness |
| **HTTP skill harness** | 83 | 83 | 100% (83/83) | Same legacy 41-skill harness exercised through the REST API |
| **Integration** | 49 | 49 | 100% (49/49) | Cross-skill consistency, boundary/adversarial, performance regression, idempotency |
| **E2E (Playwright)** | 22 | 22 | 100% (22/22) | Browser tests: all views, 14 analysis panels, 4 workflow chains, URL state |
| **Backend API pytest** | 165 | 165 | 100% (165/165) | API contracts, science helpers, and milestone 1-7 workflow endpoints including the newer researcher-facing skills |
| **Frontend Vitest** | 9 | 9 | 100% (9/9) | Frontend component / utility regression coverage |
| **Historical direct HTTP all-skill pass** | 90 | 90 | 100% (90/90) | One-by-one execution across the then-current Aug. 21, 2026 90-skill inventory via each skill's `scripts/run.py --http ...` surface |
| **Single-skill LLM inventory** | 386 | 386 | inventory coverage | Natural-language routing coverage across **100/100** skills in the current inventory |
| **Single-skill LLM (GPT-5.4 full rerun)** | 386 | 385 | 99.7% (385/386) | Latest full GPT-5.4 rerun on Saturday, August 22, 2026 across the current 386-case single-skill matrix |
| **Multi-skill orchestration inventory** | 111 | 111 | inventory coverage | Current chained-workflow inventory: 59 legacy + 52 supplemental/expansion questions |
| **Multi-skill orchestration (GPT-5.4 full rerun)** | 111 | 111 | 100% (111/111) | Latest full GPT-5.4 rerun on Saturday, August 22, 2026 across the current 111-question orchestration matrix |
| **Multi-skill orchestration (Nemotron partial rerun)** | 40 | 37 | 92.5% (37/40) | Latest Saturday, August 22, 2026 paced partial rerun before provider/model exit; useful as a health check, not a full benchmark |

All **100 documented skills** are documented in-repo. The older direct/HTTP harnesses still
cover the legacy 41-skill subset, while the current skill inventory, coverage audit, and LLM matrices
cover the current expanded surface.

Current automated coverage boundary:

- legacy direct skill harness: **41 callable skills**, **319/319 PASS**
- legacy HTTP skill harness: **41 callable skills**, **83/83 PASS**
- historical direct HTTP all-skill pass: **90/90 PASS** on the Aug. 21, 2026 90-skill inventory snapshot
- natural-language single-skill inventory: **386 cases**, **100/100 skills covered**
- latest GPT-5.4 routing rerun: **385/386 PASS**
- current orchestration inventory: **111 questions**
- latest GPT-5.4 orchestration rerun: **111/111 PASS**
- latest Nemotron partial rerun: **37/40 PASS** before provider/model exit
- the one remaining GPT-5.4 single-skill miss from that rerun (`subgraph: TP53<->E2F1`) was fixed in a targeted follow-up rerun on Saturday, August 22, 2026

Historical note: Nemotron-3-Ultra via OpenRouter was useful for finding
routing/frontmatter weaknesses. A completed paced expanded historical run reached
**79/99 PASS**, with the main persistent misses in phenotype-first planning, import-first
chaining, uncertainty/boundary explanation, and multi-strategy intervention comparison.
The latest Saturday, August 22, 2026 rerun exited before either full matrix completed, so
the current Nemotron numbers in this README should be interpreted as partial rerun health
checks rather than as new full benchmark totals.

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
