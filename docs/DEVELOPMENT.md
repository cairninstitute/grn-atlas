# Development & bootstrap

Practical guide to running, testing, and rebuilding GRN Atlas. For *what the tool does*
and the roadmap see [`ROADMAP.md`](../ROADMAP.md); to add a species see
[`ONBOARDING_SPECIES.md`](./ONBOARDING_SPECIES.md).

## Run it

```bash
# backend (FastAPI) — serves the API + reads backend/data/grn.sqlite3
cd backend && ../venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
# frontend (Vite dev server)
npm install && npm run dev            # http://localhost:3001
```

The backend needs `backend/data/grn.sqlite3` (gitignored, ~420 MB). Build it from the
fetched or locally supplied source caches (see below).

## Test

```bash
venv/bin/python -m pytest backend -q      # backend: unit + DB-invariant + API-contract
npx vitest run                            # frontend
npx vite build                            # production build sanity
npx oxlint src/...                        # lint
venv/bin/python .agents/skills/_test_all_skills.py       # 319 direct skill-harness tests across 41 legacy skills
venv/bin/python .agents/skills/_test_all_skills_http.py  # 83 HTTP skill-harness tests across the same 41 skills
venv/bin/python .agents/skills/_test_llm_single_matrix.py --provider openai --model gpt-5.4
venv/bin/python .agents/skills/_test_llm_orchestration_matrix.py --provider openai --model gpt-5.4
```

Coverage note: the dedicated skill harnesses above currently cover the legacy 41-skill
set. The repo also contains a historical direct HTTP full-surface execution pass recorded in
[`docs/skill_test_results_2026-08-21.md`](./skill_test_results_2026-08-21.md), where the
then-current 90 documented skills were executed individually through their own
`scripts/run.py --http` surface. As of **Saturday, August 22, 2026**, the current broad
LLM/coverage status is:

- **100 documented skills** in the current inventory (**99 callable + 1 overview/router**)
- **386** natural-language single-skill cases covering **100/100** skills
- **386/386 PASS** on the latest GPT-5.4 single-skill rerun, with **2 retry-recovered flaky passes**
- **111** orchestration questions in the current chained-workflow inventory
- **111/111 PASS** on the latest GPT-5.4 orchestration rerun
- **37/40 PASS** on the latest Nemotron partial orchestration rerun before provider/model exit
- A later slower Nemotron full-rerun attempt on **Saturday, August 22, 2026** failed immediately:
  Q1 failed three times at roughly 197 seconds per attempt, then Q2 failed once at roughly 197 seconds before the run was stopped

## Fetch source data, then build the database

Third-party data is **not committed** (see LICENSE). Fetch it, then build:

```bash
venv/bin/python backend/scripts/fetch_sources.py --tier light   # sources -> backend/data/; bootstraps an intermediate DB on fresh clones
venv/bin/python backend/scripts/build_db.py                     # final rebuild of grn.sqlite3 (~10 s)
venv/bin/python backend/scripts/compute_tissue_weights.py       # per-tissue coexpression (needs expression data)
```

Or equivalently: `make fetch && make db && make enrich && make tissue-weights`.

`build_db.py` is stdlib-only and glob-loads whatever caches are present in `backend/data/`
(sequence context, motif hits, pathways, traits, curated symbols) — **missing caches just
leave that layer empty**, so the core atlas always builds. Targeted loaders
(`load_seqctx.py`, `load_pathways.py`, `load_traits.py`, `load_curated_symbols.py`,
`load_connectf.py`, `load_curated_pathway_edges.py`) update an existing DB in place
without a full rebuild.

Fetch tiers (`fetch_sources.py --tier`): `core` (genes/interactions/coords/orthologs/GO/
DoRothEA/DAP-seq/gene lists, required), `light` (+ pathways/traits/seqctx/curated symbols/
PlantRegMap including rice/tobacco orthologs), `all` (also attempts the heavy layers below).

### Data sources by species

| Species | Primary | Secondary | Projection sources |
|---------|---------|-----------|-------------------|
| Human | TRRUST | DoRothEA (OmniPath) | — |
| Mouse | TRRUST | DoRothEA (OmniPath) | — |
| Arabidopsis | PlantRegMap | ATRM, DAP-seq (Plant Cistrome), ConnecTF | — |
| Tomato | PlantRegMap, Literature | — | Inferred:Arabidopsis, Inferred:Potato, Inferred:Tobacco |
| Petunia | PlantRegMap, Literature | — | Inferred:Arabidopsis, Inferred:Potato, Inferred:Tobacco |
| Rice | ConnecTF | — | Inferred:Arabidopsis (PLAZA orthologs) |
| Pepper | — | — | Inferred:Arabidopsis, Inferred:Potato, Inferred:Tobacco |
| Potato | PlantRegMap | — | — |

Hand-curated files that are committed (not fetchable): `gold_standard_{species}.tsv`,
`regulation_petunia.tsv`, `regulation_tomato.tsv`, `curated_symbols_{species}.json`,
`literature_edges_{species}.tsv`.

### Literature-curated edges

`literature_edges_{species}.tsv` files contain experimentally validated regulatory edges
from published ChIP-seq, ChIP-chip, genetics, and transactivation experiments. They use
the same 5-column format as the PlantRegMap regulation files:

```
source_id	target_id	regulation_type	confidence	literature:PMID
```

`build_db.py` automatically globs `literature_edges_*.tsv` and merges them into the
species edge lists, so adding a new literature edge is a one-line TSV append — no code
changes needed. Comment lines (starting with `#`) are skipped.

Current files:

| File | Edges | Key pathways |
|------|-------|-------------|
| `literature_edges_petunia.tsv` | 15 | MBW complex → anthocyanin structural genes (CHS-A, DFR-A, CHI-A, F3'5'H-A), PH4 → PH1 |
| `literature_edges_tomato.tsv` | 27 | RIN/FUL1/FUL2 → ripening targets (PSY1, ACS2, EXP1, NOR, CNR), WOX13 → RIN |
| `literature_edges_arabidopsis.tsv` | 10 | CBF/DREB2A → COR/RD29A, WRKY33 → PAD3/ACS2 |

### Curated gene symbols

`curated_symbols_{species}.json` maps gene IDs to human-readable names. `build_db.py`
applies these during the build, and `build_display_names.py` propagates them to the
`display_name` column. To add a new name override, add an entry to the JSON file:

```json
{
  "Solyc05g012020": {"symbol": "RIN", "source": "Literature:23386264"}
}
```

### Enrich: ConnecTF and display names (post-build)

After building the core database, run `make enrich` to layer on ConnecTF edges and
rebuild display names. This is needed only once after `make db` — the literature edges
and curated symbols are already incorporated by `build_db.py`.

```bash
# Download ConnecTF data (one-time, ~200 MB)
curl -L -o /tmp/connectf_data.tar.gz \
    https://connectf.s3.amazonaws.com/connectf_data_release_v1.tar.gz
tar xzf /tmp/connectf_data.tar.gz -C /tmp

make enrich
```

| Script | What it adds |
|--------|-------------|
| `load_connectf.py` | ~303K Arabidopsis + ~6K rice TF-target edges from ConnecTF (TARGET, ChIP-seq — DAP-seq excluded since it's already loaded). Source: Brooks et al. 2021, PMID 33631799. |
| `load_curated_pathway_edges.py` | Applies display name fixes and loads literature edges into an existing DB (same data as the TSV files, for post-build use). |
| `build_display_names.py` | 6-stage pipeline populating human-readable `display_name` for all species (see below). |

All three scripts are idempotent — safe to re-run. If ConnecTF data is not downloaded,
`make enrich` skips that step and prints download instructions.

The full bootstrap sequence is: `make fetch && make db && make enrich && make tissue-weights`.

## Compute dependencies (only for regenerating derived data)

These are **not** needed to run the app once the corresponding caches already exist
locally. A true fresh clone does not include those caches, so these tools are only needed
when you choose to regenerate the heavy layers:

- **kallisto** (expression + dsRNA transcript stores). Install a linux binary under
  `tools/kallisto/` (gitignored):
  ```bash
  curl -sL https://github.com/pachterlab/kallisto/releases/download/v0.50.1/kallisto_linux-v0.50.1.tar.gz \
    | tar xz -C tools
  ```
- **BLAST+** (curated petunia symbols via homology; regulator mapping). `tblastn`/
  `makeblastdb` under `BLAST_BIN` (default `/tmp/blastwork/ncbi-blast-2.17.0+/bin`).
- Working files (FASTA, indexes, FASTQ) live under `backend/data/expr/` and `tools/`,
  both gitignored; only the resulting JSON/`.fasta.gz` caches are committed.

Regeneration scripts (all offline-cache-producing): `fetch_seqctx.py`, `motif_scan.py`,
`fetch_expression.py`, `fetch_pathways.py`, `fetch_traits.py`, `fetch_curated_symbols.py`,
`fetch_plantregmap_regulation.py`, `build_tobacco_orthologs.py`,
`check_source_freshness.py` — driven by `backend/scripts/species_config.py`.

## Tobacco ortholog projection

Tobacco (*Nicotiana tabacum*) isn't in PLAZA, so we construct orthologs via reciprocal
best-hit BLAST against petunia, tomato, and pepper CDS. This projects ~725k tobacco
PlantRegMap edges onto the atlas species.

```bash
# Fetched automatically by fetch_sources.py --tier light, or manually:
venv/bin/python backend/scripts/fetch_plantregmap_regulation.py tobacco
venv/bin/python backend/scripts/build_tobacco_orthologs.py   # needs BLAST+
venv/bin/python backend/scripts/build_db.py                  # picks up the new orthologs
```

Requires BLAST+ (`makeblastdb`, `blastn`). Skips gracefully if BLAST+ is not installed.
Output: `backend/data/orthologs_tobacco_blast.json` (~35k pairs).

## Network validation

After building the DB, validate edge quality:

```bash
make validate
# or individually:
venv/bin/python backend/scripts/validate_regulation_quality.py   # gold-standard (94 edges)
venv/bin/python backend/scripts/validate_network_statistics.py   # population-level (all edges)
```

**Gold-standard validation** checks recall, specificity, and precision against 94
literature-curated edges (33 petunia + 38 tomato positive, 11 + 12 negative controls)
from `backend/data/gold_standard_{species}.tsv`.

**Population-level validation** runs 5 statistical tests across ALL edges per species:
regulon GO coherence, permutation significance, multi-evidence quality, expression
coherence, and motif enrichment. Reports are written to
`backend/data/network_validation_report.md`.

## Benchmarking

AUROC/AUPRC evaluation against independent ground truth:

```bash
make benchmark
# or: venv/bin/python backend/scripts/benchmark_beeline.py
```

Evaluates Arabidopsis PlantRegMap+ATRM edges against DAP-seq (AUROC=0.88) and human
DoRothEA against TRRUST. Report written to `backend/data/beeline_benchmark_report.json`.

## Tissue coexpression weights

Computes Pearson correlation between TF and target expression across tissue groups
(petunia, tomato, arabidopsis — requires expression data from the heavy tier):

```bash
make tissue-weights
# or: venv/bin/python backend/scripts/compute_tissue_weights.py
```

Populates the `edge_tissue_weights` table (~4.18M rows). Edges with |r| ≥ 0.3 are stored.
The gene detail panel shows these inline; API endpoints: `GET /api/v1/edge-tissues/{gene_id}`
and `GET /api/v1/tissues/{species}`.

## Gene display names

Plant genes use locus IDs as their primary symbol (`AT1G01010`, `Solyc02g090220.2`,
`LOC_Os01g01010`), making cross-species comparison views unreadable. The `display_name`
column in the `genes` table stores a human-readable name when one is available; the
frontend falls back to `symbol` when `display_name` is `NULL`.

```bash
cd backend
source venv/bin/activate
python scripts/build_display_names.py
```

The script is idempotent — it only fills `NULL` entries, so it's safe to re-run after
adding new genes or after a database rebuild. To force a full rebuild of all display names:

```bash
sqlite3 data/grn.sqlite3 "UPDATE genes SET display_name = NULL"
python scripts/build_display_names.py
```

### Pipeline stages (in order)

| Stage | Source | What it does |
|-------|--------|-------------|
| 1. Own symbols | Local DB | Human/mouse genes get `display_name = symbol`. Arabidopsis genes where `symbol ≠ id` get their own symbol. |
| 2. Arabidopsis orthologs | Local DB | Plant genes inherit readable names from their Arabidopsis orthologs via the `orthologs` table. |
| 3. Ensembl Plants BioMart | `plants.ensembl.org` | Bulk download of `external_gene_name` and `uniprot_gn_symbol` for Arabidopsis, tomato, and potato. New Arabidopsis names cascade to other plant species. |
| 4. UniProt TAIR | `rest.uniprot.org` | REST query for Arabidopsis genes with TAIR cross-references. Largest single source (~13k names). Results cascade to all plant species via orthologs. |
| 5. Description parsing | Local DB | Regex extraction of known gene symbols from the `name` (description) field of remaining plant genes. Also handles rice-specific patterns (`OsWRKY22`, etc.). |
| 6. Cleanup | Local DB | Removes BAC clone IDs (`F19K23.17`, `T14P4.8`) and single-character names that leaked through earlier stages. |

### Expected coverage

| Species | Coverage |
|---------|----------|
| Human | 100% |
| Mouse | 100% |
| Arabidopsis | ~52% |
| Potato | ~42% |
| Rice | ~43% |
| Tomato | ~41% |
| Pepper | ~40% |
| Petunia | ~32% |

### Notes

- **Internet access required** for stages 3 and 4 (Ensembl Plants BioMart and UniProt REST
  API). If either is unavailable the script logs the error and continues with remaining
  stages.
- **RAP-DB** (rice) is attempted by `enrich_display_names.py` but has been unreliable
  (SSL/403 errors). The consolidated `build_display_names.py` extracts rice names from
  description fields instead.
- The **Arabidopsis cascade** is the key mechanism: resolving one Arabidopsis gene name can
  propagate to tomato, petunia, potato, pepper, and rice orthologs simultaneously.
- The old two-step scripts (`migrate_display_names.py` + `enrich_display_names.py`) still
  work but are superseded by `build_display_names.py` which runs the full pipeline in one
  pass.

## Data-source currency

`GET /api/v1/provenance/freshness` (backed by `check_source_freshness.py`) reports each
source's loaded vs latest version. See the provenance manifest at `GET /api/v1/provenance`.
