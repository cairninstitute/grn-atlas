---
name: grn-projection-validation
description: "Assess whether an orthology-transferred edge has independent evidence in its recipient species. Queries cis-support scores (JASPAR motif in target promoter), chromatin peaks, and expression correlation to report what fraction of a species' projected edges are independently supported. Use for a specific edge, a TF's projected regulon, or a whole-species summary."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python). Direct database access; no HTTP endpoint.
metadata:
  author: grn-atlas
  version: "1.0"
---

## Usage

```bash
# Species-level summary: what fraction of projected edges are cis-supported?
backend/venv/bin/python .agents/skills/grn-projection-validation/scripts/run.py \
  --species tomato

# Single edge validation
backend/venv/bin/python .agents/skills/grn-projection-validation/scripts/run.py \
  --source-id Solyc02g071730.2 --target-id Solyc03g005520.2

# TF-level: all projected targets of a TF
backend/venv/bin/python .agents/skills/grn-projection-validation/scripts/run.py \
  --source-id Solyc02g071730.2 --species tomato

# All species summary
backend/venv/bin/python .agents/skills/grn-projection-validation/scripts/run.py --all
```

### Parameters
- `--species` — filter to one species
- `--source-id` — TF gene ID (with `--species`, lists all projected targets)
- `--target-id` — target gene ID (with `--source-id`, validates one edge)
- `--all` — summary across all plant species
- `--min-cis-score` (default `0.3`) — threshold for counting an edge as cis-supported
- `--db` — path to the SQLite database (default `backend/data/grn.sqlite3`)

### Output
JSON with:
- `species` — species queried
- `projected_edges` — total projected edges in scope
- `cis_supported` — edges with motif hit in target promoter (score >= threshold)
- `cis_support_rate` — fraction supported
- `edges` (when querying specific source/target) — per-edge detail with cis_score, motif_id, hit_count
- `summary` — human-readable interpretation

### How it works
Projected edges are identified by `Inferred:` in their sources field. For each,
the script checks the `cis_support_scores` table (populated by
`score_cis_support.py`) for whether the TF's JASPAR motif appears in the
target's promoter region. A cis-support score >= 0.3 means at least one motif
hit was found; higher scores reflect more hits and better motif match quality.

### Limitations
Only covers species and edges where `score_cis_support.py` has been run.
Cis-support is necessary but not sufficient evidence — a motif hit confirms
the binding site exists but not that the TF actually binds in vivo.
