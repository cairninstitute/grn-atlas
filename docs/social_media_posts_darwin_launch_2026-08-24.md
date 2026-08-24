# Social Media Posts — Darwin Launch, August 24, 2026

Recommended images for each platform noted below. All assets in `public/blog-assets/` and `darwin-validation-update-blog/`.

---

## LinkedIn — Post 1 of 3: The Launch (3,000 char limit)

**Recommended images:** gene_regulatory_network.png, grn-skill-categories.png

Introducing Darwin — an AI-powered research environment for gene regulation.

Most biological software answers one question at a time. Darwin was built for the way researchers actually work: start with a gene, a phenotype, or a regulatory hypothesis — then trace the network, compare species, evaluate evidence, predict what happens if you intervene, and decide what experiment to run next.

One workspace. From gene to hypothesis.

What Darwin covers:
- 8 species: human, mouse, Arabidopsis, tomato, petunia, pepper, potato, rice
- ~142,000 genes
- 1.47 million regulatory relationships
- Curated, inferred, and predicted evidence — always labeled separately

What Darwin can do:
- 100 structured research skills across 7 categories
- Regulatory network exploration and cross-species comparison
- Perturbation modeling and cascade prediction
- RNAi/dsRNA design and off-target screening
- Candidate ranking, evidence synthesis, and experiment prioritization
- Collaborator-ready reports, study packets, and validation plans

Darwin isn't a chatbot that happens to know genomics. It's a research system that runs real analyses against structured biological data — and tells you what's measured vs. what's inferred.

Free for academic and non-commercial use. Source-available.

Explore Darwin: https://cairninstitute.com/Darwin/
Repository: https://github.com/cairninstitute/grn-atlas
Full post: https://cairninstitute.com/blogs/Darwin/darwin-validation-update-blog/

Built by @CAIRN Institute.

#Genomics #Bioinformatics #GeneRegulation #SystemsBiology #AgenticAI #AIforScience #OpenScience #ComputationalBiology #RNAi #PlantScience #Biotech #LLMAgents #TranscriptionFactors #PlantBiology

---

## LinkedIn — Post 2 of 3: LLM Validation (3,000 char limit)

**Recommended images:** grn-llm-testing-matrix.png

How do you know an AI research tool actually works?

We tested Darwin's 100 research skills with two external LLMs — @OpenAI GPT-5.4 and @NVIDIA Nemotron-3-Ultra (via @OpenRouter) — neither fine-tuned on Darwin. The models received only skill definitions and natural-language research questions. They had to pick the right tools, extract parameters, and chain multi-step workflows on their own.

GPT-5.4 results:
- Single-skill routing: 386/386 pass
- Multi-skill orchestration: 111/111 pass

Nemotron-3-Ultra results:
- Single-skill: 255/258 pass before provider exit
- Orchestration: 37/40 pass before provider exit
- Historical full orchestration: 79/99 pass on expanded matrix

The Nemotron comparison wasn't just a benchmark — it directly improved Darwin. Routing ambiguities, skill descriptions, and workflow chaining guidance were all tightened based on where a second model struggled.

On top of LLM validation, the full deterministic test suite passes clean:
- 319/319 direct skill harness
- 83/83 HTTP skill harness
- 49/49 integration tests
- 22/22 Playwright e2e browser tests
- 165/165 backend API tests
- 9/9 frontend regression tests

Then the biological validation layer:
- Petunia gold-standard recall: 93.8% at 100% specificity
- Tomato gold-standard recall: 84.2% at 100% specificity
- Arabidopsis vs DAP-seq AUROC: 0.88
- Human DoRothEA vs TRRUST AUROC: 1.00

Three independent validation layers. One system.

https://cairninstitute.com/blogs/Darwin/darwin-validation-update-blog/

#Genomics #AgenticAI #LLMAgents #OpenAI #NVIDIA #Bioinformatics #AIValidation #GeneRegulation #ComputationalBiology #AIforScience #MachineLearning #OpenScience

---

## LinkedIn — Post 3 of 3: The Skills (3,000 char limit)

**Recommended images:** grn-skill-categories.png, dsRNA_analysis.png, hitlist_analysis.png, multi_gene_offtarget_screening.png

"Screen these RNAi candidates, pick the cleanest one, predict the perturbation effects, and summarize the affected biology."

That's not one database call. It's a multi-step research workflow.

Darwin has 100 structured research skills that turn questions like this into reproducible, testable analysis chains. Here's what they cover:

1. Orientation & data readiness — gene search, species coverage, input normalization, provenance
2. Network structure — regulons, shared regulators, pathways, centrality, modules, feed-forward loops
3. Expression & context — tissue-specific coexpression, differential regulation, boundary conditions
4. Cross-species reasoning — orthology, conservation scoring, transferability assessment
5. Perturbation & intervention — knockout/overexpression modeling, cascade prediction, combinatorial perturbation, dsRNA design, CRISPR heuristics
6. Candidate ranking & uncertainty — consensus ranking, counterfactual analysis, confidence boundaries, hypothesis comparison
7. Evidence synthesis & handoff — evidence audit, research briefs, validation plans, study packets, collaborator reports

Real workflow examples:
- grn-dsrna-screen → grn-perturbation → grn-enrichment
- grn-candidate-triage → grn-experiment-prioritization → grn-research-brief
- grn-orthology → grn-conservation → grn-transferability
- grn-research-brief → grn-validation-plan → grn-study-packet → grn-study-report

Each skill has explicit provenance: what's measured, what's inferred, what's predicted. That matters for reproducibility and for trust.

Darwin is free for academic use. Commercial licensing available.

https://cairninstitute.com/Darwin/
https://github.com/cairninstitute/grn-atlas

#Genomics #Bioinformatics #GeneRegulation #AgenticAI #RNAi #dsRNA #PlantScience #CRISPR #SystemsBiology #AIforScience #ComputationalBiology #OpenScience #Biotech

---

## Facebook — Single Post

**Recommended images:** gene_regulatory_network.png, grn-skill-categories.png, dsRNA_analysis.png, grn-llm-testing-matrix.png

Introducing Darwin — from gene to hypothesis.

Darwin is an AI-powered research environment for gene regulation from CAIRN Institute. Instead of searching databases one at a time, researchers can ask biological questions directly and Darwin coordinates the analysis.

What's inside:
- 8 species (human, mouse, Arabidopsis, tomato, petunia, pepper, potato, rice)
- ~142,000 genes and 1.47 million regulatory relationships
- 100 research skills covering network analysis, perturbation modeling, RNAi design, cross-species comparison, evidence synthesis, and experiment planning
- Measured and inferred evidence always tracked separately

How we validated it:
- GPT-5.4: 386/386 single-skill, 111/111 orchestration — perfect scores
- Nemotron-3-Ultra: 255/258 single-skill, 37/40 orchestration
- 647 deterministic tests across the full stack
- Biological benchmarks: 93.8% petunia recall, 84.2% tomato recall, both at 100% specificity
- Arabidopsis AUROC 0.88 against DAP-seq, Human AUROC 1.00 against TRRUST

Darwin isn't a chatbot with a genomics wrapper. It runs structured analyses against real biological data and tells you what's evidence vs. what's inference.

Free for academic and non-commercial use.

Explore Darwin: https://cairninstitute.com/Darwin/
Full validation post: https://cairninstitute.com/blogs/Darwin/darwin-validation-update-blog/
Repository: https://github.com/cairninstitute/grn-atlas

---

## Bluesky — Thread of 4 Posts (300 char limit each)

**Recommended images:** Post 1: gene_regulatory_network.png; Post 2: grn-skill-categories.png; Post 3: grn-llm-testing-matrix.png; Post 4: dsRNA_analysis.png

**Post 1:**
Introducing Darwin — AI-powered gene regulation research from CAIRN Institute.

8 species. 142K genes. 1.47M regulatory edges. 100 research skills. From gene to hypothesis in one workspace.

Free for academic use.
cairninstitute.com/Darwin/

**Post 2:**
Darwin's 100 skills cover: regulatory networks, perturbation modeling, RNAi/dsRNA design, cross-species conservation, candidate ranking, evidence synthesis, and collaborator-ready reports.

Measured vs inferred evidence always labeled separately.

github.com/cairninstitute/grn-atlas

**Post 3:**
Validated with external LLMs (no fine-tuning):

GPT-5.4: 386/386 single-skill, 111/111 orchestration
Nemotron-3-Ultra: 255/258 single, 37/40 orchestration

Plus biological benchmarks: 93.8% petunia recall, 0.88 Arabidopsis AUROC, 1.00 human AUROC — all at 100% specificity.

**Post 4:**
Full validation post with methodology, benchmark tables, and LLM comparison:
cairninstitute.com/blogs/Darwin/darwin-validation-update-blog/

Commercial licensing: info@cairninstitute.com

From CAIRN Institute — Advancing AI for the Public Good.

---

## Instagram — Carousel Post (2,200 char limit)

**Recommended carousel order:**
1. gene_regulatory_network.png (lead — shows the UI in action)
2. grn-skill-categories.png (shows breadth of capabilities)
3. dsRNA_analysis.png (shows RNAi design workflow)
4. multi_gene_offtarget_screening.png (shows batch screening)
5. hitlist_analysis.png (shows candidate ranking)
6. grn-llm-testing-matrix.png (shows validation results)

**Caption:**
Introducing Darwin — AI-powered gene regulation research from CAIRN Institute.

From gene to hypothesis. One workspace.

8 species | 142K genes | 1.47M regulatory edges | 100 research skills

What it does:
- Discover regulators and trace mechanisms
- Compare across species
- Predict what happens when you intervene
- Design RNAi experiments
- Rank candidates and prioritize experiments
- Generate collaborator-ready reports

How we validated it:
- @openai GPT-5.4: 386/386 single-skill, 111/111 multi-step orchestration
- @nvidia Nemotron-3-Ultra: 255/258 single, 37/40 orchestration
- Biological benchmarks: 93.8% petunia recall, 84.2% tomato recall at 100% specificity
- Arabidopsis AUROC 0.88 vs DAP-seq gold standard
- 647 deterministic tests across the full stack

Darwin doesn't just search databases. It runs structured analyses against real biological data and always tells you what's measured vs. what's inferred.

Free for academic use. Source-available.

Link in bio for the full validation post and repository.

#Genomics #Bioinformatics #GeneRegulation #SystemsBiology #AgenticAI #LLMAgents #OpenScience #ComputationalBiology #RNAi #PlantScience #AIforScience #GeneNetwork #Biotech #PlantBiology #Arabidopsis #MachineLearning #AIResearch #CRISPR #TranscriptionFactors #Petunia #Tomato #SyntheticBiology

---

## Threads — Thread of 3 Posts (500 char limit each)

**Recommended images:** Post 1: gene_regulatory_network.png; Post 2: grn-skill-categories.png; Post 3: grn-llm-testing-matrix.png

**Post 1:**
Introducing Darwin from CAIRN Institute — an AI research environment for gene regulation.

8 species. 142K genes. 1.47M regulatory edges. 100 research skills covering network analysis, perturbation modeling, RNAi design, cross-species comparison, and collaborator-ready outputs.

From gene to hypothesis.

cairninstitute.com/Darwin/

#Genomics #AgenticAI #Bioinformatics #AIforScience

**Post 2:**
What makes Darwin different: it runs real analyses against structured biological data and always distinguishes measured evidence from inference.

Skills span 7 categories — from gene search through dsRNA design, candidate ranking, validation planning, and study reports.

github.com/cairninstitute/grn-atlas

#GeneRegulation #OpenScience #ComputationalBiology

**Post 3:**
Validation results:

GPT-5.4: 386/386 single-skill, 111/111 orchestration
Nemotron: 255/258 single, 37/40 orchestration
Petunia recall: 93.8% at 100% specificity
Arabidopsis AUROC: 0.88 vs DAP-seq
Human AUROC: 1.00 vs TRRUST
Plus 647 deterministic tests.

Full post: cairninstitute.com/blogs/Darwin/darwin-validation-update-blog/

#AgenticAI #LLMAgents #Genomics

---

## Tagging Reference

| Platform | OpenAI | NVIDIA | OpenRouter | CAIRN |
|---|---|---|---|---|
| LinkedIn | @OpenAI | @NVIDIA | @OpenRouter | @CAIRN Institute |
| Facebook | @OpenAI | @NVIDIA | @OpenRouter | @CAIRN Institute |
| Bluesky | @openai.bsky.social | @nvidia.bsky.social | @openrouter.ai | — |
| Instagram | @openai | @nvidia | @openrouter | — |
| Threads | @openai | @nvidia | @openrouter | — |

## Additional Tagging Suggestions

- **Plant science**: @PlantCell, @ASPB (American Society of Plant Biologists), @ThePlantJournal
- **Bioinformatics**: @Bioinformatics (journal), @ISCB, @GalaxyProject
- **AI for science**: #AIforScience communities, @GoogleDeepMind (for visibility in AI+science space)
- **Genomics**: @ensaborigen, @NCBI, @EBI_Ensembl
- **Reproducibility**: #ReproducibleResearch, #FAIR
- **Biotech/industry**: #Biotech, #AgTech, #PlantBreeding, #CropScience
