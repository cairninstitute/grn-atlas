# CloneLab Release Validation

Date: October 23, 2026

## Release gates

| Gate | Result | Evidence |
|---|---:|---|
| Independent restriction engine | PASS | pUC19 L09137.2, eight enzymes, recognition starts, cleavage coordinates, and the complete circular fragment signature matched exactly between Biopython 1.88 and EMBOSS 6.6.0 |
| Gel migration calibration | PASS | Nine alternating held-out NEB N0550 bands; mean absolute migration error 0.004672, maximum 0.009478 of lane length |
| Indexed genome retrieval | PASS | TAIR10 and Petunia axillaris Peaxi162v1.6.2 locally indexed with checksum-verified interval retrieval |
| Arabidopsis demonstration | PASS | CCA1 promoter, TAIR10 `Chr2:19243590-19246090`; SalI distinguishes all four modeled construct states |
| Petunia demonstration | PASS | AN2 promoter, Peaxi162v1.6.2 `Peaxi162Scf00118:354537-357037`; PstI distinguishes all four modeled construct states |

Machine-readable evidence is in `validation/cross-tool-validation.json`,
`validation/gel-calibration-validation.json`, and `demos/*.json`.

## Calibration boundary

The gel profile is digitized from New England Biolabs' N0550 manufacturer reference image,
which NEB identifies as a 1.0% TBE agarose gel stained with ethidium bromide. It is measured
image data, not a gel run on CAIRN equipment. The source does not specify voltage, run time, or
lot. A local laboratory should create a separate instrument-specific calibration profile before
using predicted migration as a quantitative acceptance criterion.

## Demonstration boundary

The demonstrations connect a Darwin atlas gene to an assembly-specific promoter sequence and a
sequence-complete pUC19 construct-verification exercise. pUC19 is not a plant expression vector.
The demonstrations establish exact computational sequences, junctions, restriction fragments,
and discrimination among modeled molecular states. They do not establish promoter activity,
plant transformation, phenotype, or base-perfect construct identity.

## Reproduction

```bash
make clonelab-data
make validate-clonelab-release
venv/bin/python -m pytest backend/tests/clonelab -q
```

The independent EMBOSS gate additionally requires an EMBOSS installation with initialized
REBASE data; see `docs/DEVELOPMENT.md`.
