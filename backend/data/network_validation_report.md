# GRN Atlas — Population-Level Network Validation
Statistical validation across all regulatory edges, not just gold-standard spot-checks.
Each test uses an orthogonal data type to assess whether the inferred network
captures real biological signal.

## Summary
| Species | Edges | GO genes | Coherence (σ) | Multi-ev. z | Motif enrichment |
|---------|------:|--------:|-------------:|----------:|----------------:|
| arabidopsis | 919,449 | 17,349 | 5.08 | 4.13 | — |
| tomato | 248,288 | 12,939 | 38.57 | 1.26 | 40.35x |
| petunia | 236,727 | 11,667 | 36.26 | 2.59 | 29.38x |
| human | 17,946 | 2,041 | 7.32 | -2.25 | — |
| mouse | 17,692 | 0 | — | 0 | — |
| rice | 16,933 | 0 | — | 0 | 29.19x |
| potato | 11,409 | 0 | — | 0 | 2.8x |
| pepper | 2,212 | 0 | — | 0 | 22.29x |

## Arabidopsis

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 584
- **Mean real coherence:** 0.17329
- **Mean random coherence:** 0.16991
- **Enrichment:** 1.02×
- **Fraction of TFs above random:** 0.452

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.17281
- **Permuted mean ± std:** 0.16741 ± 0.00106
- **Effect size:** 5.08 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1242): mean overlap = 0.18005
- **Multi-source** (n=1962): mean overlap = 0.20036
- **Ratio:** 1.113×
- **Mann-Whitney z:** 4.13

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.8%
- **Random pairs coexpressed:** 0.9%
- **Rate ratio:** 0.84×
- **Mean importance (real):** 0.05202
- **Mean importance (random):** 0.05058

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
- **Mean real coherence:** 0.12961
- **Mean random coherence:** 0.10794
- **Enrichment:** 1.2×
- **Fraction of TFs above random:** 0.874

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.12963
- **Permuted mean ± std:** 0.10974 ± 0.00052
- **Effect size:** 38.57 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1265): mean overlap = 0.14289
- **Multi-source** (n=1531): mean overlap = 0.14839
- **Ratio:** 1.039×
- **Mann-Whitney z:** 1.26

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.7%
- **Random pairs coexpressed:** 0.5%
- **Rate ratio:** 1.45×
- **Mean importance (real):** 0.05292
- **Mean importance (random):** 0.06111

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 442
- **Target motif rate:** 40.3%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 40.35×
- **Median enrichment:** 32.78×
- **Fraction of TFs enriched:** 1.0


## Petunia

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 610
- **Mean real coherence:** 0.12611
- **Mean random coherence:** 0.10796
- **Enrichment:** 1.17×
- **Fraction of TFs above random:** 0.813

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.12499
- **Permuted mean ± std:** 0.10774 ± 0.00048
- **Effect size:** 36.26 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=1581): mean overlap = 0.13599
- **Multi-source** (n=1676): mean overlap = 0.1452
- **Ratio:** 1.068×
- **Mann-Whitney z:** 2.59

### Test 4 — Expression Coherence
Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression
more often than random TF-gene pairs.

- **Interaction edges coexpressed:** 0.8%
- **Random pairs coexpressed:** 0.7%
- **Rate ratio:** 1.09×
- **Mean importance (real):** 0.07028
- **Mean importance (random):** 0.05764

### Test 5 — Motif Enrichment in Inferred Targets
For TFs with known binding motifs, check whether Arabidopsis orthologs of
inferred targets have TF motif hits in promoters vs. non-targets.

- **TFs tested:** 403
- **Target motif rate:** 33.6%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 29.38×
- **Median enrichment:** 23.26×
- **Fraction of TFs enriched:** 1.0


## Human

### Test 1 — Regulon-wide GO Coherence
For each TF with ≥10 targets, measure pairwise GO term overlap among targets
vs. size-matched random gene sets.

- **TFs tested:** 191
- **Mean real coherence:** 0.06072
- **Mean random coherence:** 0.05485
- **Enrichment:** 1.11×
- **Fraction of TFs above random:** 0.471

### Test 2 — Permutation Test
Shuffle all TF→target assignments 100 times, recompute network-wide coherence.

- **Real coherence:** 0.06111
- **Permuted mean ± std:** 0.05054 ± 0.00144
- **Effect size:** 7.32 σ
- **p-value:** 0.0099

### Test 3 — Multi-evidence vs Single-source
Compare GO overlap of edges supported by 2+ independent sources vs. single-source.

- **Single-source** (n=837): mean overlap = 0.08086
- **Multi-source** (n=2000): mean overlap = 0.07014
- **Ratio:** 0.867×
- **Mann-Whitney z:** -2.25

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

- **TFs tested:** 214
- **Target motif rate:** 58.6%
- **Non-target motif rate:** 0.6%
- **Mean enrichment:** 29.19×
- **Median enrichment:** 24.85×
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

- **TFs tested:** 166
- **Target motif rate:** 5.0%
- **Non-target motif rate:** 0.9%
- **Mean enrichment:** 2.8×
- **Median enrichment:** 2.24×
- **Fraction of TFs enriched:** 0.765


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
- **Non-target motif rate:** 1.3%
- **Mean enrichment:** 22.29×
- **Median enrichment:** 18.07×
- **Fraction of TFs enriched:** 1.0


---
*Generated by `validate_network_statistics.py`*
