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
set. Newer milestone 2-7 skills are currently validated through `backend/tests/` API
tests plus targeted CLI smoke checks rather than the older `_test_all_skills*.py`
harnesses. As of **Thursday, August 13, 2026**, the current broad LLM status is:

- **347/347 PASS** on the GPT-5.4 single-skill matrix
- **59/59 PASS** on the GPT-5.4 orchestration matrix

## Fetch source data, then build the database

Third-party data is **not committed** (see LICENSE). Fetch it, then build:

```bash
venv/bin/python backend/scripts/fetch_sources.py --tier light   # sources -> backend/data/; bootstraps an intermediate DB on fresh clones
venv/bin/python backend/scripts/build_db.py                     # final rebuild of grn.sqlite3 (~10 s)
```

`build_db.py` is stdlib-only and glob-loads whatever caches are present in `backend/data/`
(sequence context, motif hits, pathways, traits, curated symbols) — **missing caches just
leave that layer empty**, so the core atlas always builds. Targeted loaders
(`load_seqctx.py`, `load_pathways.py`, `load_traits.py`, `load_curated_symbols.py`) update
an existing DB in place without a full rebuild.

Fetch tiers (`fetch_sources.py --tier`): `core` (genes/interactions/coords/orthologs/GO/
DoRothEA/gene lists, required), `light` (+ pathways/traits/seqctx/curated symbols/
PlantRegMap/tobacco orthologs), `all` (also attempts the heavy layers below).

### Data sources by species

| Species | Primary | Secondary | Projection sources |
|---------|---------|-----------|-------------------|
| Human | TRRUST | DoRothEA (OmniPath) | — |
| Mouse | TRRUST | DoRothEA (OmniPath) | — |
| Arabidopsis | PlantRegMap | ATRM (direction labels → second source) | — |
| Tomato | PlantRegMap, Literature | — | Inferred:Arabidopsis, Inferred:Potato, Inferred:Tobacco |
| Petunia | PlantRegMap, Literature | — | Inferred:Arabidopsis, Inferred:Potato, Inferred:Tobacco |
| Pepper | — | — | Inferred:Arabidopsis, Inferred:Potato, Inferred:Tobacco |
| Potato | PlantRegMap | — | — |

Hand-curated files that are committed (not fetchable): `gold_standard_{species}.tsv`,
`regulation_petunia.tsv`, `regulation_tomato.tsv`, `curated_symbols_{species}.json`.

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

## Data-source currency

`GET /api/v1/provenance/freshness` (backed by `check_source_freshness.py`) reports each
source's loaded vs latest version. See the provenance manifest at `GET /api/v1/provenance`.
