# Capability Expansion Implementation Roadmap

Date: August 13, 2026

This roadmap converts the current testing and workflow-gap analysis into a concrete implementation plan for expanding what the GRN Atlas skill layer can do for researchers. The focus is not only broader test coverage, but actual capability improvements for the kinds of questions researchers ask in practice.

## Objective

Move the system from:

- strong atlas-backed first-pass answers

to:

- more deterministic, researcher-usable workflow support for ambiguous, phenotype-driven, messy-input, and multi-constraint questions.

## Guiding principle

The next phase should prioritize capability layers that reduce orchestration fragility:

1. Normalize messy inputs before downstream analysis
2. Make phenotype-first targeting a first-class workflow
3. Improve uncertainty / failure-mode handling
4. Add stronger tradeoff-aware planning
5. Expand non-model and species-transfer support
6. Only then extend deeper biology layers such as cell-type and trajectory analysis

---

## Roadmap overview

| Milestone | Theme | Outcome |
|---|---|---|
| M1 | Input normalization | Reliable handling of messy pasted lists, CSV snippets, aliases, and mixed-species inputs |
| M2 | Phenotype-first targeting | First-class support for trait/phenotype → candidate workflow |
| M3 | Uncertainty-aware decision support | Better “what is supported / not supported / what next” behavior |
| M4 | Tradeoff-aware experiment planning | Better comparison of dsRNA, promoter edit, observational, and combinatorial strategies |
| M5 | Non-model workflow strengthening | More robust petunia/crop/non-model support |
| M6 | Literature-grounded synthesis | Better literature-to-atlas bridging with explicit evidence boundaries |
| M7 | Cell-type / trajectory readiness-plus | Better support-layer reasoning now, staged analysis support later |
| M8 | Artifact and report products | Stronger researcher-facing outputs and collaborator handoff |

---

## M1. Input normalization

### Problem

The system can handle some pasted gene lists and DEG snippets, but input cleanup is still emergent and brittle.

### Capability goal

Create a first-class preprocessing layer for user-provided inputs so downstream skills receive normalized, species-aware, mapped content.

### Proposed implementation

Add a new skill:

- `grn-input-normalization`

Responsibilities:

- normalize line-separated, comma-separated, and CSV-like pasted input
- extract candidate gene columns
- preserve unmapped rows and ambiguity
- detect likely species mixtures
- identify aliases / casing variants / duplicated entries
- emit a normalized payload for downstream skills

Suggested outputs:

- normalized gene rows
- inferred input type
- mapped rows
- ambiguous rows
- unmapped rows
- probable species distribution
- recommended next skill

### Supporting changes

- update `grn-dataset-import` frontmatter to route broad messy input to `grn-input-normalization` first
- allow downstream skills to accept normalized structured payloads

### Validation milestone

- messy alias lists
- mixed-species pasted lists
- CSV DEG tables with extra columns
- duplicate rows and case variants
- explicit partial-import success cases

### Success criteria

- normalization becomes deterministic
- downstream import analysis no longer depends on prompt luck

---

## M2. Phenotype-first targeting

### Problem

Phenotype-first questions are currently handled by long emergent chains rather than a dedicated capability.

### Capability goal

Turn “I want to change phenotype X in species Y” into a structured workflow with explicit stages and outputs.

### Proposed implementation

Add a new skill:

- `grn-phenotype-targeting`

Responsibilities:

- parse phenotype/design intent
- generate seed biological concepts or regulator families
- call literature-grounded ideation where needed
- map candidate ideas into atlas-supported genes
- score candidates for intervention relevance
- identify next recommended follow-up mode

Suggested stages:

1. phenotype parsing
2. literature cue generation
3. atlas grounding
4. candidate ranking
5. intervention readiness summary
6. confidence boundary

### Likely dependencies

- `grn-literature-review`
- `grn-candidate-triage`
- `grn-consensus-ranking`
- `grn-coverage-report`
- `grn-experiment-prioritization`

### Initial supported domains

- petunia flower color
- Arabidopsis ABA signaling
- anthocyanin / pigment regulation in supported plant species

### Validation milestone

- phenotype-first petunia color questions
- non-hit-list floral scent questions
- drought / ABA regulator targeting

### Success criteria

- phenotype-first routing is consistent
- final output is a structured candidate shortlist, not just a loose summary

---

## M3. Uncertainty-aware decision support

### Problem

The system can state evidence boundaries, but uncertainty-handling is still fragmented across several skills.

### Capability goal

Make it easier to answer:

- what is supported
- what is not supported
- what evidence is missing
- what smallest next step reduces uncertainty most

### Proposed implementation

Two approaches:

1. keep current skills and add a higher-level composition skill, or
2. expand one existing skill into a coordinator

Recommended:

- add `grn-decision-boundary`

Responsibilities:

- combine evidence audit, confidence boundary, counterfactual analysis, and minimal validation
- return a structured decision summary

Suggested output sections:

- supported now
- unsupported now
- highest-uncertainty assumptions
- overturn conditions
- smallest next validation move

### Supporting changes

- strengthen current evidence skills with consistent fields
- unify wording around support vs uncertainty vs contradiction

### Validation milestone

- mixed-evidence candidate set
- no-signal upstream regulator case
- partial-support petunia RNAi case

### Success criteria

- answers become more consistent and less prompt-sensitive
- easier to hand off to researchers without overclaiming

---

## M4. Tradeoff-aware experiment planning

### Problem

The system can recommend next experiments, but head-to-head strategy comparison is still shallow.

### Capability goal

Support real planning questions like:

- dsRNA vs promoter edit
- single-gene vs combinatorial perturbation
- observational vs intervention-first
- low budget vs medium budget

### Proposed implementation

Expand existing planning skills rather than create many new ones:

- enhance `grn-experiment-optimizer`
- enhance `grn-experiment-prioritization`

Add explicit support for:

- strategy comparison mode
- side-by-side scoring output
- constraint-aware rationale
- confidence / feasibility / interpretability dimensions

Suggested scoring dimensions:

- feasibility
- specificity
- downstream interpretability
- time-to-result
- species support
- expected signal strength

### Validation milestone

- JAF13 dsRNA vs AN2 promoter edit
- low-budget / short-timeline comparisons
- combo vs single perturbation questions

### Success criteria

- explicit comparisons, not just single recommendation lists
- consistent rationale under changing constraints

---

## M5. Non-model workflow strengthening

### Problem

Petunia and non-model workflows are improving, but still thinner and more fragile than model-organism flows.

### Capability goal

Make non-model species support more explicit, more conservative, and more useful.

### Proposed implementation

Enhance:

- `grn-coverage-report`
- `grn-transferability`
- `grn-candidate-triage`
- `grn-validation-plan`

New capability targets:

- non-model candidate readiness summaries
- model-to-non-model translation logic
- explicit “safe to infer / unsafe to infer” guidance
- intervention mode readiness by species

### Possible optional new skill

- `grn-nonmodel-translation`

Only add this if transferability + coverage + triage remain too fragmented after enhancement.

### Validation milestone

- Arabidopsis → petunia transfer questions
- petunia pigment intervention prioritization
- crop onboarding-style questions

### Success criteria

- non-model workflows stop feeling like model-organism workflows with weaker data
- species limitations are explicit and actionable

---

## M6. Literature-grounded synthesis

### Problem

Literature review exists, but bridging literature cues into atlas-supported conclusions still depends too much on long chains.

### Capability goal

Improve:

- literature extraction
- family-level cue mapping
- atlas grounding
- evidence boundary summaries

### Proposed implementation

Enhance `grn-literature-review` with:

- better phenotype query templates
- family-level candidate extraction fields
- mapped-vs-unmapped distinction
- “atlas-grounded candidates” section

Potential optional follow-on skill:

- `grn-literature-grounding`

Only if literature review grows too broad.

### Validation milestone

- flower-color gene family extraction
- anthocyanin regulator mapping
- literature + atlas TP53/BAX synthesis

### Success criteria

- fewer hallucinated mappings
- clearer difference between literature ideas and atlas-supported candidates

---

## M7. Cell-type / trajectory readiness-plus

### Problem

Current support is mainly honesty about missing layers, not actual analysis capability.

### Capability goal

Short-term:

- make readiness reporting more actionable

Long-term:

- support real cell-type and trajectory workflows when new data layers exist

### Proposed implementation

Short-term enhancements:

- expand `grn-celltype-regulation`
- expand `grn-trajectory-regulation`

Add:

- clearer missing-layer taxonomy
- suggested acquisition or onboarding steps
- species-by-species readiness breakdown

Longer-term prerequisites:

- single-cell expression support
- cell-type network support
- time-series / pseudotime data layers

### Validation milestone

- explicit unsupported-analysis cases
- onboarding-oriented planning for missing layers

### Success criteria

- current limitation is still stated honestly
- but the answer becomes more actionable for planning future capability

---

## M8. Artifact and report products

### Problem

Researchers often need shareable outputs, not just conversational answers.

### Capability goal

Improve collaborator-facing products:

- study packets
- study reports
- decision summaries
- experiment comparison outputs

### Proposed implementation

Enhance:

- `grn-study-packet`
- `grn-study-report`
- `grn-research-brief`

Add support for:

- phenotype-first summaries
- uncertainty summaries
- strategy comparison sections
- species limitations sections

### Validation milestone

- collaborator handoff for phenotype-first petunia question
- uncertainty-aware decision summary
- comparative strategy report

### Success criteria

- outputs become directly reusable in real collaboration

---

## Recommended implementation order

### Phase 1: High leverage / low-to-medium complexity

1. M1 Input normalization
2. M2 Phenotype-first targeting
3. M4 Tradeoff-aware experiment planning

Reason:

- these directly improve the highest-friction researcher workflows
- they also reduce orchestration fragility

### Phase 2: Better scientific decision support

4. M3 Uncertainty-aware decision support
5. M6 Literature-grounded synthesis
6. M5 Non-model workflow strengthening

Reason:

- these improve trustworthiness and applied value

### Phase 3: Deeper future-facing expansion

7. M7 Cell-type / trajectory readiness-plus
8. M8 Artifact and report products

Reason:

- these are valuable, but depend more on future data/model layers or packaging work

---

## Suggested sprint structure

### Sprint A

- implement `grn-input-normalization`
- wire `grn-dataset-import` routing to it
- add expanded messy-input tests

### Sprint B

- implement `grn-phenotype-targeting`
- scope first version to petunia color + Arabidopsis ABA use cases
- add phenotype-first orchestration tests

### Sprint C

- expand `grn-experiment-optimizer` and `grn-experiment-prioritization` for explicit strategy comparison
- add tradeoff comparison tests

### Sprint D

- implement `grn-decision-boundary`
- add negative-result / uncertainty tests

### Sprint E

- enhance literature grounding and non-model transferability flows
- add applied-species synthesis tests

---

## New-skill recommendation summary

Recommended to implement:

- `grn-input-normalization`
- `grn-phenotype-targeting`
- `grn-decision-boundary`

Conditional / optional:

- `grn-nonmodel-translation`
- `grn-literature-grounding`

These latter two should only be added if enhanced versions of current skills remain too fragmented.

---

## Validation strategy

Each milestone should be validated at three levels:

1. single-skill routing and argument tests
2. orchestration workflow tests
3. HTTP/UI workflow checks where applicable

Each capability milestone should also include:

- at least one supported-species happy path
- at least one partial-support case
- at least one unsupported or failure-boundary case

---

## Success definition

This roadmap succeeds if, after implementation:

- phenotype-first questions become structured and consistent
- messy user input is normalized deterministically
- uncertainty handling becomes explicit and reusable
- tradeoff questions return real comparisons
- non-model species workflows become more actionable and safer
- researcher-facing outputs become easier to reuse directly

