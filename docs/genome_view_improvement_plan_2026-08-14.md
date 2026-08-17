# Genome View Improvement Plan

Date: August 14, 2026

Purpose: preserve the current assessment of the Advanced tools → Genome view so it can be revisited after the initial public release.

## Current assessment

The genome view is visually interesting, but in its current form it is more of an ortholog-ribbon visualization than a high-utility analysis surface.

What it currently does well:

- gives a quick visual sense that two genomes have many or few mapped ortholog links
- lets the user click a symbol and trace that symbol across both genomes
- works as a lightweight “where are the mapped genes” display

Why it currently feels limited:

- it mixes all ortholog links into one dense picture
- it does not summarize what is conserved versus merely linked
- it does not distinguish important differences from background clutter
- it is chromosome-centric, while many researcher questions are gene-centric or pathway-centric

## Highest-value improvements

### 1. Add filter modes

Useful controls to add:

- show only 1:1 orthologs
- show only synteny anchors
- show only selected-gene neighborhood
- show only TFs
- hide many-to-many links
- minimum conservation/support threshold

Expected value:

- immediate reduction in visual clutter
- much easier interpretation for human↔mouse and plant↔plant comparisons

### 2. Add a gene-centered comparison mode

For a selected gene such as JAF13, show:

- the gene in species A
- its ortholog(s) in species B
- nearby genes / local block
- whether local regulators/targets are conserved

Expected value:

- much more useful than a whole-genome ribbon plot for actual research workflows

### 3. Add summary panels above the plot

Suggested summary stats:

- total ortholog pairs
- 1:1 count
- 1:n / n:m count
- synteny-supported count
- unmapped genes in each species
- top duplicated families

Expected value:

- turns similarities and differences into explicit, readable information

### 4. Make differences first-class

Useful researcher-facing outputs:

- genes in A with no ortholog in B
- duplicated in B but single-copy in A
- same ortholog but different network role
- conserved gene but non-conserved regulon

Expected value:

- supports “what changed?” questions directly instead of only visual browsing

### 5. Add local conservation scoring

For a selected gene or gene set, score:

- ortholog confidence
- synteny support
- neighborhood overlap
- regulon overlap
- pathway overlap

Expected value:

- makes the view useful for decision support rather than only navigation

### 6. Replace dense ribbons with selectable modes

Better alternatives for large comparisons:

- chromosome heatmap of ortholog density
- dot plot by chromosome pair
- block-level synteny segments
- per-gene table + linked mini-view

Expected value:

- better signal-to-noise than thousands of ribbon paths

## Recommended implementation order

1. filter modes
2. summary stats
3. selected-gene comparison mode
4. difference-first outputs
5. local conservation scoring
6. alternative visualization modes

## Release recommendation

Do not block the current release on this work.

The genome view is acceptable as a visually interesting exploratory surface for the current release, but it should be treated as a post-release improvement area rather than a finished conservation-analysis workflow.
