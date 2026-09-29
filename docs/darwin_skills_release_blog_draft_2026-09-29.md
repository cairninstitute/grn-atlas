# Darwin Skills: Structured AI Workflows for Gene Regulation

Author: CAIRN Institute

Published: Draft, September 29, 2026

Read time: 8-10 minutes

#Genomics #GeneRegulation #Bioinformatics #SystemsBiology #AIforScience #PlantScience

## Quick Summary

Darwin is a research system for working with gene regulatory networks: who regulates a gene, what evidence supports an edge, which regulators explain a gene set, what might change after perturbation, and which experiment is most useful next.

This release makes that system available as a structured skill layer for AI agents. Darwin now provides **100 documented skills**: **99 callable research skills** and one overview/router. The skills expose the atlas through defined tools rather than asking a model to improvise database queries or biological claims from memory.

We tested two different things:

| Evaluation | What it measures | GPT-5.6 Terra result |
| --- | --- | ---: |
| Single-skill evaluation | Can the model choose and execute the right tool for one natural-language request? | 386/386 (100%) |
| Orchestration evaluation | Can the model complete a multi-step research workflow, use the required tool chain, and produce the requested conclusion? | 111/111 (100%) |

On the 111-task orchestration suite, Opus 4.6 reached **107/111 (96.4%)** and Nemotron-3 Ultra reached **95/111 (85.6%)**.

These are tool-use and workflow-reliability results. They do not establish that every network prediction is biologically correct. Biological validity requires the separate evidence, benchmark, and experimental layers in the atlas.

## Why a Skill Layer

Gene-regulation questions are rarely one lookup.

A researcher may begin with a set of differentially expressed genes, ask which transcription factors explain it, check whether the conclusion transfers to a different species, assess the evidence for a candidate edge, and then choose between RNAi, CRISPR, or a promoter edit. Each step has different inputs, assumptions, and failure modes.

General-purpose language models are useful interfaces, but an unconstrained chat response is not a reliable research workflow. Darwin's skill layer gives the agent specific operations, arguments, and return values for each task. That makes the work inspectable and lets us test the workflow rather than relying on an answer that merely sounds plausible.

## What Researchers Can Do

The skill layer covers the major phases of a regulatory-biology project.

| Workflow area | What the skills support | Representative skills |
| --- | --- | --- |
| Find and inspect | Resolve gene names, inspect records, retrieve local networks, regulons, paths, subgraphs, modules, and network motifs | gene search, network, regulon, pathfinding, subgraph, modules |
| Interpret a gene set | Import and normalize lists, identify upstream regulators, run GO/pathway/trait enrichment, and score TF or pathway activity | dataset import, upstream, enrichment, regulon enrichment, TF activity |
| Add biological context | Retrieve expression and coexpression, compare tissues or cell types, analyze trajectories, and inspect signaling-to-TF relationships | expression, coexpression, cell-type regulation, trajectory drivers, signaling-to-TF |
| Evaluate evidence | Audit network, motif, chromatin, enhancer, perturbation, and multi-omic support for a gene or edge | evidence audit, cis-support audit, multiome audit, chromatin support, enhancer network |
| Work with regulatory DNA | Query promoter motifs, map peaks to genes, inspect genomic context, prioritize promoter edits, and assess variants | motif query, peak-gene linkage, genome browser, promoter-edit prioritization, variant effect |
| Design interventions | Predict perturbation consequences, compare combinations and modalities, design dsRNA or CRISPR guides, and assess off-target risk | perturbation, combinatorial perturbation, dsRNA, CRISPR design, CRISPR-vs-dsRNA comparison |
| Compare species | Find orthologs, assess edge conservation, quantify transfer risk, rescue sparse evidence, and assess readiness | orthology, conservation, transferability, family rescue, coverage report |
| Decide and hand off | Rank candidates, identify the smallest defensible validation step, build plans, and preserve provenance | candidate triage, decision boundary, validation plan, research brief, provenance |

The point is not to replace experimental judgment. It is to make the computational reasoning chain explicit: what was queried, what was returned, what evidence is missing, and what should be tested next.

## Single-Skill Testing

The single-skill matrix contains **386 natural-language cases** spanning the full documented skill inventory. A case asks for one concrete research task, such as finding a gene, extracting a regulon, checking promoter support, designing dsRNA, comparing intervention modes, or importing an omics table.

Each case checks whether the model selected the appropriate tool, supplied required arguments, successfully executed the tool against the atlas, and met task-specific output constraints where relevant.

GPT-5.6 Terra completed **386/386** cases. This is a validated composite result: 384 cases passed in the matrix run, and the final two were replayed after correcting a species-name boundary issue. Terra had supplied the scientifically valid name Arabidopsis thaliana; the dsRNA API expected the internal canonical key arabidopsis. The API and grader now canonicalize standard species synonyms, and the dsRNA regression suite passed 10/10.

## Orchestration Testing

The orchestration suite contains **111 multi-step questions**. They require the agent to select a sequence of skills, carry information from one step to the next, and state the requested conclusion in its final answer. One useful tool call is not enough when a prompt requires follow-up analysis.

The suite includes:

- gene discovery followed by network, regulon, evidence, or enrichment analysis;
- imported omics data followed by differential, cell-state, trajectory, or TF activity analysis;
- promoter, motif, chromatin, and variant or edit-consequence follow-up;
- RNAi or CRISPR design followed by off-target, perturbation, and pathway analysis;
- inferred-edge comparison followed by curated-network or module validation;
- orthology, conservation, transferability, and family-rescue analysis;
- phenotype-first candidate discovery, literature grounding, prioritization, readiness assessment, and validation planning; and
- decision-boundary, counterfactual, calibration, and collaborator-handoff workflows.

## Orchestration Results

| Model | Transport | Result | Interpretation |
| --- | --- | ---: | --- |
| GPT-5.6 Terra | ChatGPT-authenticated Codex CLI with structured MCP tools | 111/111 (100%) | Validated composite result on the current routing and MCP configuration |
| Opus 4.6 | Claude CLI with native MCP tools | 107/111 (96.4%) | Strong completion; four misses were incomplete chains or semantically similar but incorrect tool choices |
| Nemotron-3 Ultra | OpenRouter | 95/111 (85.6%) | Useful performance, with more incomplete multi-step work and final-synthesis errors |

GPT Terra was clean on the current suite. Opus was close, but most of its four misses involved stopping one tool short of the expected chain or selecting a nearby analysis. Nemotron's 16 misses clustered around incomplete multi-step work, final synthesis, and a small number of wrong routes. These findings are actionable: they identify where routing instructions, tool interfaces, or evaluation cases need further hardening.

## What These Results Do and Do Not Mean

The results support a narrow but important claim: with structured access to Darwin's research tools, models can be evaluated for reliable tool use and workflow completion rather than assessed only by the fluency of their prose.

They do not mean that an LLM has independently proved a regulatory edge, predicted an in vivo phenotype, or replaced a biological experiment. Darwin's outputs should be interpreted as atlas-grounded hypotheses with visible evidence, uncertainty, and follow-up steps.

## Practical Bottom Line

Darwin now offers a structured way to move from a research question to a regulatory hypothesis, evidence audit, intervention plan, or collaborator-ready report across the atlas's supported species and data layers.

The strongest current tool-use result is GPT-5.6 Terra at **386/386** single-skill cases and **111/111** orchestration cases. Opus 4.6 and Nemotron-3 Ultra provide additional evidence that the skill layer is portable across model families, while also showing where longer research chains remain challenging.

Explore Darwin: https://www.cairninstitute.com/Darwin/

Learn more about CAIRN Institute: https://www.cairninstitute.com/

