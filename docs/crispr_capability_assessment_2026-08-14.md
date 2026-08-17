# CRISPR Capability Assessment and Post-Release Roadmap

Date: August 14, 2026

Purpose: document the current CRISPR functionality in GRN Atlas, assess how it compares with the dsRNA tooling, and preserve a concrete post-release improvement roadmap.

## Executive summary

GRN Atlas currently has real CRISPR functionality, but it is much narrower and less mature than the dsRNA workflow.

Current state:

- there is a backend CRISPR guide-design endpoint
- there is a `grn-crispr-design` skill
- there is workflow integration for lightweight guide suggestions

However, the current implementation is best described as:

- sequence-first
- heuristic
- lightweight
- not yet a full researcher-facing CRISPR design workflow

In contrast, the dsRNA tooling already behaves much more like a complete applied workflow:

- target selection
- specificity assessment
- off-target framing
- screen-many ranking
- predicted downstream perturbation context
- comparative decision support

That means CRISPR exists, but is not yet at parity with dsRNA as a practical intervention-design surface.

## What exists now

### Implemented capability

- API endpoint: `/api/v1/crispr/design`
- skill: `grn-crispr-design`
- workflow integration in the assay-design step

### Current behavior

The present implementation supports:

- guide suggestion from an input DNA sequence
- PAM-aware scanning
- lightweight heuristic prioritization of guides

### Current limitations

The present implementation does not yet provide:

- genome-wide off-target search
- transcript/gene-first CRISPR design from atlas IDs
- species-aware locus retrieval and guide generation without pasted sequence
- editing-mode distinctions such as knockout vs promoter perturbation vs precise regulatory editing
- downstream experimental framing on the same level as dsRNA
- comparison/ranking of multiple CRISPR strategies for a candidate set
- integrated “what would this edit likely do?” reasoning beyond adjacent workflow steps

## Why dsRNA currently feels much stronger

The dsRNA workflow is already organized around the researcher’s actual task:

- identify candidate genes
- screen multiple targets
- find the cleanest intervention window
- assess off-target burden
- compare candidates side by side
- predict downstream effects
- interpret likely biological consequences

CRISPR currently only covers one segment of that chain well:

- guide suggestion from sequence

So the gap is not that CRISPR is absent. The gap is that CRISPR is not yet organized as a full intervention workflow.

## Main gap categories

### 1. Entry-point gap

Current CRISPR is sequence-first.

Researchers often want:

- “design guides for this gene”
- “design promoter-edit guides for this regulatory site”
- “compare CRISPR strategies for these candidates”

The current workflow requires more manual sequence preparation than dsRNA.

### 2. Specificity/off-target gap

dsRNA already has explicit off-target logic that is central to the user experience.

CRISPR currently lacks:

- genome-level off-target search
- mismatch-tolerant off-target ranking
- clear specificity summaries
- side-by-side comparison of guide cleanliness

### 3. Edit-intent gap

CRISPR workflows are not all the same. Researchers may want:

- coding knockout
- promoter editing
- motif disruption
- enhancer/site perturbation
- CRISPRi-like repression planning

The current implementation does not yet frame guides around edit intent strongly enough.

### 4. Species-context gap

For CRISPR to feel native in GRN Atlas, it should work from atlas-native gene and promoter context across supported species.

Right now, CRISPR is much closer to a generic sequence utility.

### 5. Decision-support gap

The dsRNA panel helps decide among candidates.

CRISPR currently does not yet provide:

- multi-guide ranking for an intended biological goal
- candidate-vs-candidate CRISPR strategy comparison
- workflow-level interpretation of guide consequences

## Recommended post-release roadmap

### Phase 1 — Make CRISPR gene-first instead of sequence-first

Goal:

- allow the user to start from a gene, promoter site, or atlas result rather than needing to paste sequence

Suggested work:

- resolve atlas gene ID → genomic locus → sequence window
- allow “design guides for current focus gene”
- allow “design promoter-edit guides for the selected site”
- surface species-aware sequence retrieval in the workflow UI

Success criteria:

- researcher can design guides from a selected atlas gene without manual sequence preparation

### Phase 2 — Add explicit guide-quality and off-target scoring

Goal:

- bring CRISPR specificity reasoning closer to the current dsRNA standard

Suggested work:

- mismatch-based off-target search within the relevant species genome
- simple risk tiers for off-target burden
- guide-level specificity summary
- screen-many mode for comparing candidate genes or candidate sites

Success criteria:

- researcher can compare multiple guides or multiple targets and understand which are cleaner

### Phase 3 — Add edit-intent-specific workflows

Goal:

- move beyond generic guide suggestions

Suggested work:

- coding-region knockout mode
- promoter/motif disruption mode
- regulatory-site editing mode integrated with `grn-promoter-edit-prioritization`
- sequence-window recommendations tailored to the selected edit goal

Success criteria:

- CRISPR guide suggestions are meaningfully different depending on the intervention objective

### Phase 4 — Add comparison and decision support

Goal:

- make CRISPR selection a workflow, not just a list of guides

Suggested work:

- compare guides side by side
- compare CRISPR vs dsRNA for the same candidate
- compare CRISPR strategies across multiple candidate genes
- add ranked “recommended first intervention” summaries

Success criteria:

- the user can answer “which CRISPR strategy should I try first?” from the UI

### Phase 5 — Connect guide design to network consequences

Goal:

- make CRISPR feel integrated with the rest of GRN Atlas

Suggested work:

- connect guide design to promoter-edit prioritization
- connect likely edit target to perturbation/cascade logic
- explain whether the edit is expected to reduce, increase, or alter regulation of downstream programs

Success criteria:

- CRISPR design is linked to predicted network interpretation, not isolated from it

## Highest-priority concrete improvements

If only a small amount of post-release work is available, the highest-value items are:

1. gene-first CRISPR design from atlas context
2. off-target specificity scoring
3. promoter-edit workflow integration
4. guide comparison / ranking

These four changes would close most of the practical usability gap relative to dsRNA.

## Recommended product framing at release

For the current public release, CRISPR should be described accurately as:

- available
- sequence-based
- lightweight
- useful for preliminary guide suggestion
- not yet at parity with the dsRNA design workflow

That is a defensible release position and avoids overstating current capability.

## Release recommendation

Do not block the release on CRISPR expansion.

The current dsRNA tooling is already a stronger flagship intervention workflow. CRISPR should be treated as a real but limited capability in the release, with the roadmap above reserved for post-release development.
