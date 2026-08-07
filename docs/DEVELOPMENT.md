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
```

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

Fetch tiers (`fetch_sources.py --tier`): `core` (genes/interactions/coords/orthologs/GO,
required), `light` (+ pathways/traits/seqctx/curated symbols), `all` (also attempts the
heavy layers below).

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
`check_source_freshness.py` — driven by `backend/scripts/species_config.py`.

## Data-source currency

`GET /api/v1/provenance/freshness` (backed by `check_source_freshness.py`) reports each
source's loaded vs latest version. See the provenance manifest at `GET /api/v1/provenance`.
