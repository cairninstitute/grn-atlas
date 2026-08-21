# GRN Atlas — Population-Level Network Validation
Statistical validation across all regulatory edges, not just gold-standard spot-checks.
Each test uses an orthogonal data type to assess whether the inferred network
captures real biological signal.

## Summary
| Species | Edges | GO genes | Coherence (σ) | Multi-ev. z | Motif enrichment |
|---------|------:|--------:|-------------:|----------:|----------------:|
| arabidopsis | 919,449 | 17,349 | 1.71 | 0.28 | — |
| tomato | 248,288 | 12,939 | 35.17 | 2.36 | 38.55x |
| petunia | 236,727 | 11,667 | 30.25 | 2.08 | 29.53x |
| human | 17,946 | 2,041 | 6.82 | -2.24 | — |
| mouse | 17,692 | 0 | — | 0 | — |
| rice | 16,933 | 0 | — | 0 | 27.99x |
| potato | 11,409 | 0 | — | 0 | 3.33x |
| pepper | 2,212 | 0 | — | 0 | 28.5x |

## Arabidopsis

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 584
- **Mean real coherence:** 0.17323
- **Mean random coherence:** 0.16991
- **Enrichment:** 1.02×
- **Fraction of TFs above random:** 0.486

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.17512
- **Permuted mean ± std:** 0.17295 ± 0.00127
- **Effect size:** 1.71 σ
- **p-value:** 0.0396

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1234): mean overlap = 0.19956
- **Multi-source** (n=1961): mean overlap = 0.20015
- **Ratio:** 1.003×
- **Mann-Whitney z:** 0.28

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 1.0%
- **Random pairs coexpressed:** 0.8%
- **Rate ratio:** 1.23×
- **Mean importance (real):** 0.05067
- **Mean importance (random):** 0.0502

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 0
- no TFs with both motifs and inferred targets


## Tomato

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 730
- **Mean real coherence:** 0.12968
- **Mean random coherence:** 0.10795
- **Enrichment:** 1.2×
- **Fraction of TFs above random:** 0.881

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.12929
- **Permuted mean ± std:** 0.10831 ± 0.0006
- **Effect size:** 35.17 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1245): mean overlap = 0.13585
- **Multi-source** (n=1547): mean overlap = 0.1443
- **Ratio:** 1.062×
- **Mann-Whitney z:** 2.36

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.6%
- **Random pairs coexpressed:** 0.6%
- **Rate ratio:** 0.94×
- **Mean importance (real):** 0.05797
- **Mean importance (random):** 0.05757

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 442
- **Target motif rate:** 40.3%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 38.55×
- **Median enrichment:** 29.89×
- **Fraction of TFs enriched:** 1.0


## Petunia

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 610
- **Mean real coherence:** 0.12611
- **Mean random coherence:** 0.10779
- **Enrichment:** 1.17×
- **Fraction of TFs above random:** 0.826

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.12618
- **Permuted mean ± std:** 0.10828 ± 0.00059
- **Effect size:** 30.25 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1578): mean overlap = 0.13587
- **Multi-source** (n=1661): mean overlap = 0.14653
- **Ratio:** 1.078×
- **Mann-Whitney z:** 2.08

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 1.1%
- **Random pairs coexpressed:** 0.6%
- **Rate ratio:** 1.68×
- **Mean importance (real):** 0.06272
- **Mean importance (random):** 0.05862

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 402
- **Target motif rate:** 33.6%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 29.53×
- **Median enrichment:** 24.92×
- **Fraction of TFs enriched:** 1.0


## Human

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 191
- **Mean real coherence:** 0.06079
- **Mean random coherence:** 0.05475
- **Enrichment:** 1.11×
- **Fraction of TFs above random:** 0.487

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.06085
- **Permuted mean ± std:** 0.05032 ± 0.00154
- **Effect size:** 6.82 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=813): mean overlap = 0.08445
- **Multi-source** (n=2000): mean overlap = 0.06992
- **Ratio:** 0.828×
- **Mann-Whitney z:** -2.24

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 0
- no TFs with both motifs and inferred targets


## Mouse

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 0
- **Mean real coherence:** 0
- **Mean random coherence:** 0
- **Enrichment:** None×
- **Fraction of TFs above random:** 0

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0
- **Permuted mean ± std:** 0.0 ± 0.0
- **Effect size:** 0.0 σ
- **p-value:** 1.0

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=0): mean overlap = 0
- **Multi-source** (n=0): mean overlap = 0
- **Ratio:** None×
- **Mann-Whitney z:** 0

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 0
- no TFs with both motifs and inferred targets


## Rice

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 0
- **Mean real coherence:** 0
- **Mean random coherence:** 0
- **Enrichment:** None×
- **Fraction of TFs above random:** 0

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0
- **Permuted mean ± std:** 0.0 ± 0.0
- **Effect size:** 0.0 σ
- **p-value:** 1.0

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=0): mean overlap = 0
- **Multi-source** (n=0): mean overlap = 0
- **Ratio:** None×
- **Mann-Whitney z:** 0

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 216
- **Target motif rate:** 59.0%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 27.99×
- **Median enrichment:** 25.86×
- **Fraction of TFs enriched:** 1.0


## Potato

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 0
- **Mean real coherence:** 0
- **Mean random coherence:** 0
- **Enrichment:** None×
- **Fraction of TFs above random:** 0

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0
- **Permuted mean ± std:** 0.0 ± 0.0
- **Effect size:** 0.0 σ
- **p-value:** 1.0

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=0): mean overlap = 0
- **Multi-source** (n=0): mean overlap = 0
- **Ratio:** None×
- **Mann-Whitney z:** 0

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 167
- **Target motif rate:** 4.9%
- **Non-target motif rate:** 0.8%
- **Mean enrichment:** 3.33×
- **Median enrichment:** 2.07×
- **Fraction of TFs enriched:** 0.725


## Pepper

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 0
- **Mean real coherence:** 0
- **Mean random coherence:** 0
- **Enrichment:** None×
- **Fraction of TFs above random:** 0

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0
- **Permuted mean ± std:** 0.0 ± 0.0
- **Effect size:** 0.0 σ
- **p-value:** 1.0

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=0): mean overlap = 0
- **Multi-source** (n=0): mean overlap = 0
- **Ratio:** None×
- **Mann-Whitney z:** 0

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.0%
- **Random pairs coexpressed:** 0.0%
- **Rate ratio:** None×
- **Mean importance (real):** 0
- **Mean importance (random):** 0

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 45
- **Target motif rate:** 70.0%
- **Non-target motif rate:** 0.9%
- **Mean enrichment:** 28.5×
- **Median enrichment:** 31.77×
- **Fraction of TFs enriched:** 1.0


---
*Generated by `validate_network_statistics.py`*
