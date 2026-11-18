# Source redistribution classification

Each data source in the atlas is classified by whether its raw data may be
redistributed (archived in a release artifact or Zenodo deposit).

## Redistributable

These sources allow redistribution of derived data or are openly licensed:

| Source | License/Terms | Notes |
|--------|--------------|-------|
| AGRIS AtRegNet | Public domain (USDA) | Downloaded TSV committed to repo |
| DirectBinding | Generated locally | DAP-seq peak overlaps computed from committed data |
| Perturbation sign consensus | Derived | Computed from perturbation_observations |
| Conserved signed orthology | Derived | Computed from orthologs + signed interactions |
| ConnecTF experiment evidence | CC-BY 4.0 | Brooks et al. 2024 |
| Expression Atlas | CC-BY 4.0 (EMBL-EBI) | Reviewed perturbation experiments |

## Not redistributable (fetch required)

These sources require the user to fetch from the upstream API at build time:

| Source | Terms | Reason |
|--------|-------|--------|
| CollecTRI (via OmniPath) | Academic use; cite Türei et al. | OmniPath terms prohibit bulk redistribution |
| SIGNOR | Academic use; cite Lo Surdo et al. | SIGNOR terms require direct download |
| ChIP-Atlas | CC-BY-NC 4.0 | Non-commercial clause prevents unrestricted redistribution |
| TFLink | Academic use | Download terms require registration/acceptance |
| PlantTFDB | Academic use; cite Jin et al. | No explicit redistribution permission |
| ReMap | CC-BY-NC-SA 4.0 | Non-commercial, share-alike |
| UniBind | CC-BY-NC 4.0 | Non-commercial clause |

## Reproducibility guarantee

The atlas offers **content-identical builds from archived inputs** for the
redistributable subset, and **structurally equivalent builds within declared
tolerances** for sources that must be re-fetched.

Specifically:
- `make bootstrap` from a fresh clone reproduces the database
- `backend/scripts/content_digest.py` computes a content hash of the built database
- `backend/scripts/verify_release_data.py` checks table counts against tightened floors
- All Python dependencies are pinned with `==` in `requirements.txt`
- Random seeds are fixed (`--seed 42`) in inference scripts
- `source_import_runs` records sha256 hashes for 14 of 18 imports

What we do NOT claim:
- **Bit-identical builds**: SQLite page layout, timestamps, and row ordering
  may vary across runs
- **Identical re-fetches**: OmniPath, SIGNOR, and other live APIs may return
  updated data, changing edge counts within the declared tolerances
