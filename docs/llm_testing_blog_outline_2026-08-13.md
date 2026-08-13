# Blog Outline: GRN Atlas Skills, LLM Testing Coverage, and Remaining Gaps

Date: August 13, 2026

This document is a blog-oriented outline of what the GRN Atlas skills can do today, what kinds of questions have been tested against LLM orchestration, and what remains untested or only lightly tested.

## 1. Framing

Possible framing for a blog post:

- The GRN Atlas is not just a database of gene regulatory interactions.
- It is exposed through a skill layer that allows an LLM to use the atlas as an analysis environment.
- The key question is not only whether the atlas contains useful data, but whether an LLM can reliably choose the right skill, chain multiple skills, and complete realistic research workflows.
- Current testing shows strong coverage for core atlas operations and a growing but still incomplete coverage of open-ended research planning workflows.

## 2. What the skills can do

The current skill set supports several major classes of work.

### A. Find and orient genes in the atlas

The skills can:

- search for genes by symbol, alias, keyword, or partial name
- retrieve detailed gene records
- identify whether a gene is a transcription factor
- inspect species availability and atlas-wide statistics
- retrieve provenance, sources, methods, and citations

Research value:

- helps the user move from a vague gene name to an atlas-ready identifier
- supports collaborator handoff, manuscript writing, and reproducibility

### B. Explore regulatory network structure

The skills can:

- list regulators and targets of a gene
- find paths between genes
- identify shared regulators of multiple genes
- extract subgraphs
- compare regulons
- compute centrality
- detect motifs like feed-forward loops
- detect network modules
- inspect inferred regulatory edges and compare them with curated edges

Research value:

- supports mechanistic interpretation
- helps prioritize candidate regulators
- enables network-level reasoning instead of isolated gene lookups

### C. Add expression and context layers

The skills can:

- retrieve expression profiles
- identify coexpressed genes
- compare regulatory activity across tissues or conditions
- report whether cell-type and trajectory-level analyses are currently supported

Research value:

- helps distinguish theoretical network relationships from context-relevant ones
- supports tissue-aware and condition-aware prioritization

### D. Reason across species

The skills can:

- find orthologs
- compare network conservation between species
- assess whether a conclusion is transferable across species

Research value:

- supports translation from model organisms to crops or ornamentals
- helps identify where cross-species inference is plausible and where it is weak

### E. Plan interventions

The skills can:

- design dsRNA for RNAi
- rank multiple genes by dsRNA designability and off-target burden
- simulate perturbation effects
- model cascades
- compare combinatorial perturbations
- analyze promoter variants
- prioritize promoter edit targets
- suggest CRISPR guides
- suggest primer pairs

Research value:

- takes the user from candidate genes to actionable intervention ideas
- supports both screening-style and follow-up experiment planning

### F. Interpret gene sets and guide follow-up

The skills can:

- run GO/pathway/trait/motif enrichment
- import a gene list
- perform first-pass gene-set analysis
- rank candidate genes
- audit evidence
- produce confidence boundaries
- compare competing hypotheses
- generate consensus rankings
- build validation plans, study packets, study reports, and research briefs
- review external literature
- generate species onboarding plans

Research value:

- supports triage, prioritization, planning, and communication
- begins to move the atlas toward a research copilot rather than only a query tool

## 3. What has been tested

There are two major testing layers in the current repo.

### A. Single-skill routing tests

Purpose:

- test whether the LLM picks the correct skill and arguments for a prompt

Current scale:

- 324 total single-skill questions

What these tests cover well:

- gene search and lookup
- network neighborhood queries
- pathfinding and subgraphs
- enrichment
- perturbation
- dsRNA design and dsRNA screening
- orthology and conservation basics
- centrality, modules, motifs, and exports
- provenance, citations, and atlas orientation

What this means:

- the system has substantial coverage for direct atlas operations
- the model has been tested on many narrow but important decision boundaries between adjacent skills

### B. Multi-skill orchestration tests

Purpose:

- test whether the LLM can chain multiple skills to complete a realistic workflow

Current scale:

- 43 orchestration questions

These tests cover workflows such as:

- shared regulator discovery
- RNAi design -> perturbation -> enrichment
- regulon comparison -> enrichment
- cross-species conservation analysis
- species selection -> centrality -> coexpression
- DEG set -> upstream regulator ranking -> path validation
- motif / network pattern workflows
- Cytoscape-style export workflows
- ortholog comparison workflows
- provenance-aware reporting
- experimental planning workflows
- inferred-edge validation against curated network structure

What this means:

- the testing goes beyond one-shot queries
- the LLM is being tested on whether it can complete research tasks that require sequencing several steps correctly

### C. HTTP-level testing

There is also HTTP/API testing to ensure that the underlying atlas endpoints and skill surfaces behave correctly outside the LLM layer.

Research value of this layer:

- distinguishes model-routing problems from backend correctness problems
- helps confirm that an LLM failure is not simply an API failure

## 4. What appears well tested

The best-covered areas today are:

- core gene lookup and atlas orientation
- local network interpretation
- regulatory topology workflows
- perturbation and RNAi-oriented workflows
- enrichment-based interpretation
- basic cross-species reasoning
- provenance/citation/export workflows

If writing this for a launch-oriented audience, a defensible statement would be:

- The current test coverage is strongest for the practical workflows a researcher would use when moving from a candidate gene to a network-backed interpretation and then to a first-pass intervention plan.

## 5. What has not been tested enough yet

These are the main thin spots.

### A. Open-ended biological ideation

Examples:

- "Which genes are the best targets for changing flower color in petunia?"
- "What is the best intervention point for this phenotype?"

Current status:

- partially supported
- not yet deeply covered in the automated suites

Why it matters:

- this is closer to how many researchers actually ask questions
- it requires combining literature, atlas evidence, ranking, and uncertainty communication

### B. Negative-result and weak-signal workflows

Examples:

- "Nothing strong came back. What should I try next?"
- "Which conclusion is least uncertain?"

Current status:

- lightly tested

Why it matters:

- research often fails to produce a clear winner
- the system should be tested on what it does when the atlas evidence is incomplete or inconclusive

### C. Real-world dataset ingestion messiness

Examples:

- malformed CSVs
- aliases mixed with stable IDs
- mixed-species gene lists
- user DEG tables with extra columns or inconsistent formatting

Current status:

- only lightly represented

Why it matters:

- real users do not hand the system perfectly formatted input

### D. Comparative experimental decision-making

Examples:

- dsRNA vs promoter editing
- single-gene knockdown vs combinatorial perturbation
- low-budget vs higher-confidence validation plans

Current status:

- some pieces exist
- direct head-to-head testing is still thin

Why it matters:

- researchers often need tradeoff-aware recommendations, not just one valid next step

### E. Applied species-specific workflows

Examples:

- ornamentals such as petunia
- crop transfer workflows
- non-model organism interpretation

Current status:

- present, but much thinner than human and Arabidopsis coverage

Why it matters:

- one of the most distinctive value propositions is using the atlas beyond the standard model-organism workflow

### F. Cell-type and trajectory analysis beyond readiness reporting

Current status:

- readiness and gap-reporting exist
- full biological analysis workflows are not yet deeply test-covered

Why it matters:

- this is a likely area of future expansion

## 6. Suggested honest positioning

For public-facing writing, a strong but accurate framing would be:

- The skills already support a broad set of gene regulatory network workflows, including candidate lookup, network interrogation, perturbation planning, RNAi design, enrichment, orthology, provenance, and research-brief generation.
- The strongest automated testing today is around skill routing, network analysis, RNAi and perturbation workflows, and multi-step atlas-backed chains.
- The thinner areas are the most open-ended and human-like research questions: ambiguous prompts, negative results, messy imported datasets, tradeoff-heavy planning, and phenotype-driven ideation in non-model species.

That framing is accurate and does not overstate current validation.

## 7. Useful blog sections to draft later

Possible section headings:

- What the GRN Atlas skills make possible
- How we tested LLM use of the skills
- What kinds of workflows already work well
- Where the current limits still are
- Why testing skill chaining matters for research copilots
- What we plan to test next

## 8. Possible “what we plan to test next” bullets

- more phenotype-first prompts
- more petunia and non-model workflows
- more literature-grounded ranking tasks
- more messy-import dataset cases
- more negative-result and uncertainty workflows
- more experiment tradeoff questions
- more end-to-end applied research scenarios

## 9. Short conclusion draft

The current GRN Atlas skill layer is already capable of supporting a meaningful set of research workflows through an LLM interface. The most mature areas are atlas navigation, network interpretation, perturbation and RNAi planning, enrichment, and cross-species support. The next testing frontier is not basic functionality but realism: open-ended biological questions, messy inputs, uncertain evidence, and decision-making under real research constraints.

