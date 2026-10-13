# External signed regulatory evidence

GRN Atlas stores newly imported evidence in `regulatory_evidence` before any
decision to promote it into the backward-compatible `interactions` graph. This
prevents direct TF-target evidence, perturbation responses, signaling causality,
and orthology-transferred predictions from becoming indistinguishable.

## Evidence layers

- `direct_signed`: activation or repression supported as a TF-target relation.
- `direct_unsigned`: direct binding/regulation without a defensible sign.
- `perturbation_signed`: a context-specific expression response to perturbation.
- `causal_signaling`: a causal molecular relation that is not necessarily TF-DNA regulation.
- `orthology_transferred`: an edge projected from another species.

The legacy `interactions` table remains unchanged by external imports. Promotion
must be an explicit, separately reviewed operation after identifier, overlap, and
sign-conflict benchmarks.

## Reproducible imports

```bash
make external-regulation
backend/venv/bin/python backend/scripts/audit_provenance_manifest.py
backend/venv/bin/python backend/scripts/discover_plant_perturbations.py \
  --output docs/benchmarks/plant-perturbation-discovery.json
backend/venv/bin/python backend/scripts/validate_literature_edges.py
backend/venv/bin/python backend/scripts/audit_connectf_coverage.py \
  /tmp/connectf_data_release_v1 \
  --output docs/benchmarks/connectf-coverage-audit.json
```

`load_external_regulatory_sources.py` currently supports:

- CollecTRI human signed TF-target evidence from OmniPath.
- SIGNOR's dedicated human/mouse transcriptional-relations export.
- AGRIS AtRegNet rows restricted to `Direct`, `Confirmed`, and explicitly signed records.

Raw third-party downloads and the generated SQLite database are intentionally not
committed. Import runs record source URL, version, fetch time, SHA-256 checksum,
parse counts, and status in `source_import_runs`.

## Current benchmark

The checked benchmark artifacts are `docs/benchmarks/external-signed-evidence.json`
and `.csv`. Pair-level results from the current atlas build are:

| Source | Mapped records | Unique pairs | New pairs | Existing-sign agreements | Existing-sign conflicts | Source-internal conflicts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CollecTRI | 44,784 | 42,923 | 35,186 | 7,271 | 186 | 126 |
| SIGNOR | 2,686 | 2,551 | 1,507 | 991 | 41 | 10 |
| AGRIS AtRegNet | 3,837 | 3,563 | 2,912 | 132 | 22 | 274 |

Internal conflicts generally represent studies or contexts assigning opposite signs
to the same mapped pair. They are preserved as separate records and are not eligible
for automatic graph promotion.

The ConnecTF coverage audit reproduces all 330,903 Arabidopsis and 6,137 rice pairs
in the current database, with no missing gene endpoints. The Expression Atlas
catalogue scan found 12 rice and 3 tomato differential-study candidates; these remain
discovery records until their contrasts and regulator identifiers are reviewed.

KnockTF is loaded as a separate perturbation layer: 1,572,511 human observations
across 440 TFs, 310,990 mouse observations across 115 TFs, and 106,926 Arabidopsis
observations across 18 TFs. `make knocktf` derives perturbation signs only for
Arabidopsis; human and mouse observations are not implicitly promoted into graph signs.

## Sparse-species curation

For tomato, petunia, potato, and pepper, literature curation uses five-column TSV:

```text
TF_GENE_ID<TAB>TARGET_GENE_ID<TAB>activation|repression<TAB>0..1<TAB>literature:PMID
```

Run `validate_literature_edges.py` before rebuilding. It rejects invalid signs,
confidence values, citations, duplicate records, and genes absent from the named
species. Absence of a curated file is reported explicitly rather than interpreted
as evidence that the species has no regulation.
