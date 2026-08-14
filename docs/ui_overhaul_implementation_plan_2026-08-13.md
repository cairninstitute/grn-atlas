# UI Overhaul Implementation Plan

Date: August 13, 2026

Status: Initial workflow-first overhaul implemented on Thursday, August 13, 2026.

## Objective

Move the GRN Atlas frontend from a panel-first demo-style UI to a workflow-first research workspace that reflects the current skill architecture.

## Problems the overhaul addresses

1. the old UI was organized around tabs and isolated panels rather than realistic research entry modes
2. shared researcher context such as species, focus gene, candidate set, and comparison groups was too fragmented
3. phenotype-first, dataset-first, and decision-support workflows were underrepresented in the information architecture
4. the skill layer had significantly outgrown the UI model

## Target success criteria

The overhaul is considered successful when:

1. users can begin from gene, dataset, phenotype, or decision intent
2. shared context persists across the app
3. candidate sets and workflow artifacts are visible as app-level state rather than only panel-local state
4. advanced tool panels remain reachable without defining the primary UX
5. the UI structure mirrors the actual researcher workflows supported by the skill layer

## Implementation phases

### Phase 1. Shared research-session state

Implemented:

- `src/state/ResearchSessionContext.jsx`
- `src/state/researchSessionReducer.js`

Responsibilities:

- persist species
- persist focus gene
- persist intent
- persist candidate set
- persist mapped gene IDs
- persist phenotype question
- persist comparison groups
- persist artifact status

### Phase 2. Workflow-first app shell

Implemented:

- primary workflow navigation in `src/components/app/AppNavigation.jsx`
- persistent context bar in `src/components/context/ResearchContextBar.jsx`
- workflow-first home screen in `src/components/home/HomeWorkspace.jsx`

Primary entry modes:

1. Start from a gene
2. Start from a list
3. Start from a phenotype
4. Decide and hand off
5. Advanced tools

### Phase 3. Dedicated workflow screens

Implemented:

- `src/components/workflows/GeneWorkflow.jsx`
- `src/components/workflows/DatasetWorkflow.jsx`
- `src/components/workflows/PhenotypeWorkflow.jsx`
- `src/components/workflows/DecisionWorkflow.jsx`

Design choice:

- reuse the existing `WorkflowWorkspace` backend wiring
- expose focused workflow subsets through `visibleSections`
- preserve the legacy advanced views during migration

### Phase 4. Advanced-tools containment

Implemented:

- legacy explorer, organism, paths, orthology, genome, design, and analysis views now live under `Advanced tools`
- legacy tabs remain available only within that advanced area

This keeps power-user access while removing those tools as the primary navigation model.

### Phase 5. WorkflowWorkspace refactor for reuse

Implemented:

- section gating with `visibleSections`
- custom hero metadata
- optional example cards
- session synchronization callback for app-level state

Section model:

- context
- phenotype
- import
- analysis
- consensus
- planning
- differential
- literature
- design
- advanced

## Current architecture after this pass

### Top-level shell

- `src/GeneNetworkExplorer.jsx`
  - owns app mode
  - owns advanced subview
  - owns legacy selected-gene/network state
  - bridges old panel views with new workflow state

### Shared state

- `ResearchSessionProvider`
  - synchronizes workflow outputs upward
  - exposes cross-workflow context in one place

### Primary UX

- Home
- Gene workflow
- Dataset workflow
- Phenotype workflow
- Decision workflow

### Legacy UX

- available under Advanced tools

## Validation completed

Validated on Thursday, August 13, 2026:

- frontend tests: `17/17 PASS`
- production build: PASS

Commands used:

```bash
npm test
npm run build
```

## Remaining follow-up work

This pass establishes the new information architecture and shared state foundation. Follow-up improvements that remain worthwhile:

1. richer artifact drawer instead of status-only context chips
2. deeper gene-workflow-specific visualizations embedded directly into the workflow page
3. better code-splitting for the large frontend bundle
4. broader end-to-end workflow tests across the new navigation model
5. eventual decomposition of `WorkflowWorkspace.jsx` into smaller section components

## Files changed in the overhaul pass

- `src/GeneNetworkExplorer.jsx`
- `src/components/WorkflowWorkspace.jsx`
- `src/components/ViewTabs.jsx`
- `src/components/app/AppNavigation.jsx`
- `src/components/context/ResearchContextBar.jsx`
- `src/components/home/HomeWorkspace.jsx`
- `src/components/workflows/GeneWorkflow.jsx`
- `src/components/workflows/DatasetWorkflow.jsx`
- `src/components/workflows/PhenotypeWorkflow.jsx`
- `src/components/workflows/DecisionWorkflow.jsx`
- `src/state/ResearchSessionContext.jsx`
- `src/state/researchSessionReducer.js`
- `src/styles/AppShell.css`

## Practical outcome

The frontend now matches the actual shape of the GRN Atlas skill system much more closely:

- workflow-first by default
- persistent research context
- clearer entry paths for realistic researcher tasks
- advanced panels preserved but demoted from primary UX
