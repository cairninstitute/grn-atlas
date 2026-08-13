# LLM Testing Workflow Coverage Notes

Date: August 13, 2026

This note captures the current summary of what kinds of questions are being asked in the GRN Atlas LLM test suites, how those questions map to researcher workflows, and where the main testing gaps remain. It is intended as a durable reference for future planning, reporting, or blog-writing.

## Test suite structure

There are two broad classes of LLM test questions in the repo:

1. Single-skill routing questions: 334 total
2. Multi-skill orchestration questions: 53 total

Single-skill questions test whether the model picks the correct skill and arguments for one prompt.

Multi-skill orchestration questions test whether the model chains multiple skills together to complete a realistic research workflow.

## Representative single-skill question types

- Gene lookup / search
  - "Search for the gene TP53 in humans and show me the top 5 results."
  - "Find MYB genes in Arabidopsis. Show me at most 3 results."

- Gene detail / TF status
  - "Look up MDM2. Is it a transcription factor and what species is it from?"

- Local network questions
  - "Show me all the regulators and targets of TP53 in the gene regulatory network."
  - "What transcription factors regulate TP53? Show only its upstream regulators."

- Enrichment
  - "Run Gene Ontology enrichment analysis on these genes: TP53, BAX, BCL2, CDKN1A, MDM2."
  - "What pathways are enriched among TP53, BAX, BCL2, CDKN1A, and MDM2?"

- Expression / coexpression
  - "What is the expression profile for HY5 (AT5G11260)?"
  - "Find the top 10 genes coexpressed with HY5 (AT5G11260)."

- Perturbation
  - "What would happen if TP53 were knocked out? Simulate the perturbation."
  - "Simulate overexpression of TP53. What genes would be affected?"

- dsRNA / RNAi
  - "Design a dsRNA construct to silence ABF1 (AT1G49720) in Arabidopsis."
  - "Analyze this 48-nucleotide sequence for potential off-target siRNAs in Arabidopsis."

- Orthology / conservation
  - "What is the mouse ortholog of TP53?"
  - "Is the HY5 regulatory network conserved between Arabidopsis and petunia?"

- Regulon / upstream regulators
  - "Show me the full regulon of TP53 at depth 1 -- all its direct targets."
  - "Find the upstream regulators of BAX, BCL2, and CDKN1A in human."

- Differential regulation / inferred edges
  - "Which TFs are differentially active between root and inflorescence in Arabidopsis?"
  - "What TFs are predicted by GRNBoost2 to regulate HY5 in Arabidopsis?"

- Provenance / citations / export / motifs / modules / centrality / stats
  - questions about data sources, DOIs, motif hits, network modules, hub TFs, exports, and atlas statistics

## Single-skill coverage by workflow

| Workflow | Cases | What it covers | Assessment |
|---|---:|---|---|
| Network topology | 93 | local neighborhoods, paths, subgraphs, motifs, centrality, modules, regulons, upstream/shared regulators, inferred edges, differential regulation | Strong |
| Gene lookup / atlas orientation | 69 | gene search, gene info, species, stats, provenance, citations, atlas overview | Strong |
| Intervention design | 55 | dsRNA, dsRNA screening, perturbation, cascades, combinatorial perturbation, promoter edit / CRISPR / primer follow-up | Strong |
| Functional interpretation | 45 | GO/pathway/trait/motif enrichment, export for downstream tools | Strong |
| Expression context | 23 | expression, coexpression, differential expression, cell-type readiness, trajectory readiness | Moderate |
| Cross-species reasoning | 22 | orthology, conservation, transferability | Moderate |
| Research planning | 27 | triage, evidence audit, coverage report, validation plans, research briefs, literature review, consensus ranking, onboarding plans, messy import, phenotype-first planning boundaries | Moderate |

## Multi-skill orchestration categories

The orchestration suite covers these categories:

1. Network intersection / shared regulators
2. RNAi experiment pipeline
3. Regulon comparison + enrichment
4. Cross-species conservation
5. Species discovery -> centrality -> coexpression
6. Upstream regulator analysis + validation
7. Network patterns + subgraph
8. Gene lookup -> perturbation -> enrichment
9. Cross-species RNAi screen
10. Cascade modeling
11. Ortholog comparison pipeline
12. Database orientation + focused analysis
13. Expression-guided network analysis
14. Regulon comparison across TF families
15. Provenance-aware analysis
16. Export pipeline for downstream tools
17. Multi-perturbation + comparison
18. Arabidopsis cross-species regulatory conservation
19. Autoregulation + centrality analysis
20. Full experimental design pipeline
21. Inferred-network validation chain
22. Phenotype-first / literature-guided petunia ideation
23. Weak-signal / uncertainty handling
24. Messy import and first-pass recovery
25. Experimental tradeoff comparison
26. Non-model species readiness + ranking
27. Literature-grounded mapping into atlas
28. Honest species/coverage boundary explanation
29. Strategy comparison: single vs combo perturbation
30. Unsupported-analysis boundary quality
31. Mixed-species import boundary

## Representative orchestration questions

- "I want to silence HY5 in Arabidopsis using RNAi. First check if a dsRNA can be designed for it, then tell me what downstream genes would be affected if HY5 is knocked out, and what GO terms are enriched in those targets."

- "Is the TP53->BAX regulatory relationship conserved in mouse? Find the regulatory path from TP53 to BAX in humans, and check if a similar path exists in mouse."

- "Find inferred regulatory edges for HY5 (AT5G11260) in Arabidopsis using GRNBoost2. For the top predicted regulators, check whether they also appear in the curated network as known regulators of HY5."

- "Import this human hit list: TP53, BAX, and MDM2. Import the list into the atlas, then run a first-pass gene-set analysis and tell me the top ranked candidate and the top predicted upstream regulator."

- "For HY5 (AT5G11260), assess whether a promoter variant at position 1900 with A to G overlaps a motif-supported regulatory site. Then prioritize the best promoter edit targets and suggest both CRISPR guides and primer pairs for follow-up."

## Practical assessment

Well covered right now:

- single-gene atlas questions
- network interpretation
- RNAi/dsRNA workflows
- perturbation + enrichment chains
- orthology/conservation basics
- provenance/citation/export workflows
- phenotype-first petunia prompting at a first-pass level
- messy import recovery at a first-pass level
- explicit capability/readiness boundary reporting

Relatively thin right now:

- literature-grounded hypothesis generation beyond first-pass ranking
- ambiguous or underspecified researcher prompts
- negative-result workflows beyond basic confidence-boundary handling
- multi-step comparison among several experimental strategies with hard tradeoffs
- cell-type / trajectory analysis beyond readiness reporting
- planning workflows under realistic lab constraints
- user-uploaded dataset heterogeneity beyond simple pasted-list and CSV-like cases
- phenotype-to-candidate workflows for traits other than petunia flower-color

## Updated gaps from a researcher-usage perspective

1. Open-ended biological intent questions
   - Example: "What are the best genes to change petunia flower color?"
   - Current coverage: moderate first-pass coverage now exists
   - Missing: stronger support for other phenotypes, stronger multi-branch follow-up, and more deterministic phenotype-to-candidate routing

2. Failure / uncertainty handling
   - Example: "No strong regulator is found -- what should I do next?"
   - Current coverage: moderate first-pass coverage now exists
   - Missing: more cases with conflicting evidence, partial support, and explicit model behavior under no-signal conditions

3. Real dataset ingestion
   - Example: DEG tables, malformed CSVs, aliases, mixed species IDs
   - Current coverage: improved from thin to moderate
   - Missing: larger real-world tables, extra metadata columns, duplicate rows, alias collisions, and multi-file upload-style cases

4. Experimental tradeoff decisions
   - Example: dsRNA vs promoter edit vs observational validation under budget/time constraints
   - Current coverage: improved from light to moderate
   - Missing: broader comparison across more than two strategies, stronger grading for explicit tradeoff reasoning, and phenotype-specific decision frameworks

5. Comparative phenotype workflows
   - Example: "Which intervention is most likely to alter pigment without broad pleiotropy?"
   - Current coverage: still partial
   - Missing: pleiotropy-aware prioritization, phenotype-specific effect scoring, and broader non-model phenotype coverage

6. Species-specific applied workflows
   - Petunia / crop / non-model use is now materially better covered, but still much thinner than human + Arabidopsis coverage

## Areas where current ability is still weak

These are workflows where the atlas can often provide a partial answer, but the capability is still weak or fragile:

- phenotype-first ideation outside the currently exercised petunia flower-color space
- broad literature-to-atlas grounding for noisy or indirect phenotype concepts
- realistic lab tradeoff planning across several competing intervention modes
- cell-type and trajectory questions that ask for actual biological conclusions rather than readiness reporting
- strong handling of messy experimental uploads beyond short pasted text
- robust explanation of why an analysis failed when multiple species, aliases, or data layers are mixed

## Areas where current ability is limited or effectively absent

These are workflows where the current system mostly cannot provide the full researcher-facing functionality yet:

- full cell-type regulatory analysis from single-cell or spatial layers
- full trajectory-resolved regulatory analysis
- reliable phenotype-to-target recommendation for broad trait domains without relying on heuristic literature chaining
- rich multi-file dataset ingestion and normalization as a first-class workflow
- causal confidence estimates that go beyond current network/evidence heuristics
- strong experimental design support for unsupported species without first onboarding new data layers

## Practical interpretation

The system now covers substantially more of the "questions researchers actually ask" surface than it did before the expansion, especially for:

- petunia phenotype-first workflows
- uncertainty-aware responses
- messy import recovery
- readiness and support-boundary explanation
- simple intervention tradeoff comparisons

The main remaining limitation is not the absence of basic atlas functions. It is the gap between:

- a correct first-pass atlas-backed answer, and
- a robust, deterministic research-copilot answer for messy, ambiguous, phenotype-driven, multi-constraint workflows.

## Suggested future use

This note should be useful for:

- blog drafting
- release notes
- test roadmap planning
- skill gap analysis
- explaining current LLM evaluation scope to collaborators
