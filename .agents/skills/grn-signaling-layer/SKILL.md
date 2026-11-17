---
name: grn-signaling-layer
description: "Query the protein-level regulatory layer: curated causal edges where one protein changes another's activity, held separately from the transcriptional graph and excluded from it by design. Use to ask what a protein regulates post-translationally, which signalling proteins reach a transcription factor, or how separate transcriptional cores are linked by signalling. Human and mouse only. Prefer grn-network, grn-regulon or grn-upstream for transcriptional regulation; use this when the question names kinases, phosphorylation, receptors, signalling cascades, or how a signal reaches a TF."
compatibility: Requires the grn-atlas backend virtualenv (backend/venv/bin/python). Needs the regulatory_layer_edges table, populated by migrate_signor_layers.py. Direct database access only; there is no HTTP endpoint for this layer.
metadata:
  author: grn-atlas
  version: "1.1"
---

## Usage

```bash
backend/venv/bin/python .agents/skills/grn-signaling-layer/scripts/run.py --summary
backend/venv/bin/python .agents/skills/grn-signaling-layer/scripts/run.py --gene-id AKT1
backend/venv/bin/python .agents/skills/grn-signaling-layer/scripts/run.py --gene-id JUN --direction upstream
backend/venv/bin/python .agents/skills/grn-signaling-layer/scripts/run.py --gene-id JUN --trace --depth 2
```

### Parameters
- `--summary` — what the layer holds, by species, layer and source. Start here.
- `--gene-id` — the gene to inspect.
- `--trace` — walk upstream from `--gene-id`. Read `saturated` before quoting
  `reached_count`; see "Reading a trace" below.
- `--depth` (default 2, with `--trace`) — hops to walk. 3 and above saturate.
- `--direction` (`both`, `upstream`, `downstream`; default `both`)
- `--species` (`human`, `mouse`) — omit and it is derived from the gene. If the
  id exists in both, the result carries `species_ambiguous` and mixes them.
- `--min-confidence` (default 0.0)
- `--limit` (default 200) — edges returned per direction. Counts are always over
  everything found, never over the returned payload; `upstream_truncated` and
  `downstream_truncated` say when there is more than was returned.
- `--layers` — accepted, but see "One layer only" below. Filtering is a no-op today.

### Output
JSON. `gene_known: false` with an `error` means the id is not in the `genes`
table — an unresolved identifier, *not* an absence of curated signalling. A known
gene with zero counts is a genuine absence. Never report the first as the second.

For `--summary`, counts by species, layer, relation and source. For a gene,
upstream and downstream edges with sign, confidence, source, PMIDs and whether each
partner is a TF, plus true counts and truncation flags. For `--trace`, the genes
reached, flagged by TF status, with `reached_fraction` and `saturated`.

## What this layer is

Curated causal relations that are **not transcription**: one protein changing
another's activity. 19,098 edges — 13,165 human, 5,933 mouse — all from SIGNOR
via OmniPath, covering 8,272 genes of which 669 are TFs. Human and mouse share no
gene ids, so the layer is two disjoint graphs; the largest connected component is
4,952 genes, about 95% of the human layer. Counts are as of 2026-11-16.

These were previously loaded into `interactions` and labelled transcriptional,
which inflated the human feedback core from roughly 1,000 genes to over 3,000.
The November 2026 migration moved them here and excluded them from the observed
signed graph.

## One layer only

Every edge is `protein_activity`. There are no `protein_degradation`,
`complex_formation` or `post_transcriptional` edges, even though
`multilayer_control.VALID_LAYERS` permits them. The layer is derived from
OmniPath's interaction *type*, and all of SIGNOR's non-transcriptional records
arrive as `post_translational`, which maps to `protein_activity`.

Mechanism detail — phosphorylation versus ubiquitination versus cleavage — is not
in the OmniPath `interactions` endpoint that built this table. Distinguishing
activity from degradation would require querying enzyme-substrate data, which has
not been done. So `--layers` filtering cannot currently separate anything, and an
answer must not imply that a `protein_activity` edge is specifically not a
degradation event. It means "post-translational, mechanism unrecorded".

## Reading a trace

Depth 1 and 2 are seed-specific and readable: a hub kinase reaches tens at depth 1
and a few hundred at depth 2, a sparsely-connected gene reaches one and seven.

At depth 3 the numbers stop being about the seed. Three unrelated hubs — SRC, JUN
and AKT1 — reach 919, 907 and 911 genes, within 1.3% of each other: about 18% of
the human layer each, while a single-edge gene reaches 88. Reach is still
seed-dependent, but a thousand genes is not an answer to "what regulates this
protein". Above
`reached_fraction` 0.10 the result carries `saturated: true` and a warning; report
those as reachability, not as the gene's regulators.

## Routing notes

- Transcriptional regulation — who regulates this gene, what does this TF target —
  is `grn-network`, `grn-regulon` or `grn-upstream`. Not this skill.
- `grn-signaling-to-tf` traces receptors to TFs through the **transcriptional**
  network. This skill traces the **protein** layer. They answer different
  questions and can disagree; always say which layer an answer came from.
- For feedback structure spanning both layers, use `grn-feedback-control` with
  `--include-multilayer`. In human that view adds 25 cross-core macro-circuits
  absent from the transcriptional graph.

## Evidence boundary

A path here is a documented mechanism, not a measured rate. The layer carries no
timing, no magnitude, no mechanism detail, and no guarantee that two edges are
active in the same cell or condition. It is populated for human and mouse only and
is empty for every plant species. An empty result means no curated edge, not an
absence of signalling.
