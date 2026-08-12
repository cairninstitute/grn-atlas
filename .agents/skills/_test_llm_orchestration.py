#!/usr/bin/env python3
"""
LLM skill-orchestration test harness for GRN Atlas.

Sends complex multi-step biology questions to an LLM (via OpenRouter),
exposes all GRN Atlas skills as callable tools, lets the model call them
iteratively, and grades the final synthesized answer.

Usage:
    export OPENROUTER_API_KEY=sk-or-...
    backend/venv/bin/python .agents/skills/_test_llm_orchestration.py

Options:
    --model MODEL_ID    OpenRouter model (default: nvidia/nemotron-3-ultra-550b-a55b:free)
    --http URL          Pass through to skills (use running server instead of direct DB)
    --verbose           Print full conversation traces
    --question N        Run only question N (1-indexed)
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
PYTHON = str(REPO_ROOT / "backend" / "venv" / "bin" / "python")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
MAX_TOOL_ROUNDS = 10

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "grn_gene_search",
            "description": "Search for genes by name, symbol, or keyword. Returns matching genes with id, symbol, name, species, gene_type, is_tf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (gene name, symbol, or keyword)"},
                    "species": {"type": "string", "description": "Filter by species (human, mouse, arabidopsis, tomato, petunia)"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_gene_info",
            "description": "Get detailed info about a gene by ID or symbol. Returns id, symbol, name, species, gene_type, is_tf, synonyms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Gene ID (e.g. TP53, AT5G11260)"},
                    "symbol": {"type": "string", "description": "Gene symbol (requires species)"},
                    "species": {"type": "string", "description": "Species name (needed with symbol)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_network",
            "description": "Get regulators and/or targets of a gene with confidence scores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Gene ID"},
                    "direction": {"type": "string", "enum": ["both", "regulators", "targets"], "description": "Which neighbors (default: both)"},
                    "min_confidence": {"type": "number", "description": "Min confidence (default 0.3)"},
                },
                "required": ["gene_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_pathfinding",
            "description": "Find regulatory paths between two genes via BFS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source gene ID"},
                    "target": {"type": "string", "description": "Target gene ID"},
                    "max_depth": {"type": "integer", "description": "Max path length (default 3)"},
                    "min_confidence": {"type": "number", "description": "Min edge confidence"},
                },
                "required": ["source", "target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_enrichment",
            "description": "Run overrepresentation analysis (GO, pathway, trait, motif) on a gene set.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "type": {"type": "string", "enum": ["go", "pathway", "trait", "motif"], "description": "Enrichment type"},
                },
                "required": ["gene_ids", "type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_expression",
            "description": "Get expression profile (TPM per sample) for a gene.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Gene ID"},
                },
                "required": ["gene_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_coexpression",
            "description": "Find top co-expressed genes by Pearson correlation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Gene ID"},
                    "top": {"type": "integer", "description": "Number of top partners (default 20)"},
                    "min_r": {"type": "number", "description": "Min absolute correlation (default 0.5)"},
                },
                "required": ["gene_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_perturbation",
            "description": "Predict downstream effects of knocking out or overexpressing a gene.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Gene ID to perturb (single gene)"},
                    "gene_ids": {"type": "string", "description": "Multi-intervention: comma-separated gene:action pairs (e.g. TP53:ko,MYC:oe)"},
                    "action": {"type": "string", "enum": ["ko", "oe"], "description": "ko=knockout, oe=overexpress (for single gene)"},
                    "depth": {"type": "integer", "description": "Propagation depth (default 4)"},
                    "min_confidence": {"type": "number", "description": "Min edge confidence"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_subgraph",
            "description": "Extract the induced regulatory subgraph for a gene set.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_orthology",
            "description": "Find cross-species orthologs with their regulatory networks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Gene ID"},
                    "species": {"type": "string", "description": "Target species (comma-separated for multiple)"},
                },
                "required": ["gene_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_conservation",
            "description": "Analyze conservation of regulatory edges between two species.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs (species A)"},
                    "species_b": {"type": "string", "description": "Species to compare against"},
                },
                "required": ["gene_ids", "species_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_cascade",
            "description": "Predict regulatory cascade effects from upstream interventions on a target gene.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_gene": {"type": "string", "description": "Gene ID to predict cascade on"},
                    "interventions": {"type": "string", "description": "Comma-separated tf_id:direction:magnitude (e.g. SIRT1:up:1.5)"},
                    "depth": {"type": "integer", "description": "Cascade depth (default 3)"},
                },
                "required": ["target_gene", "interventions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_regulon",
            "description": "Extract the full regulon of a transcription factor (all direct+indirect targets).",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "TF gene ID"},
                    "depth": {"type": "integer", "description": "Expansion depth (default 2)"},
                    "min_confidence": {"type": "number", "description": "Min edge confidence"},
                },
                "required": ["gene_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_regulon_compare",
            "description": "Compare two TFs' regulons: overlap, Jaccard, statistical significance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tf_a": {"type": "string", "description": "First TF gene ID"},
                    "tf_b": {"type": "string", "description": "Second TF gene ID"},
                    "depth": {"type": "integer", "description": "Regulon depth (default 2)"},
                    "min_confidence": {"type": "number", "description": "Min edge confidence"},
                },
                "required": ["tf_a", "tf_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_upstream",
            "description": "Predict which TFs best explain a gene set (upstream regulator analysis).",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "species": {"type": "string", "description": "Species name"},
                    "depth": {"type": "integer", "description": "Regulon depth (default 1)"},
                    "top": {"type": "integer", "description": "Max results (default 50)"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_stats",
            "description": "Get atlas-wide or per-species statistics (gene counts, interaction counts, TF counts).",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species for per-species stats (omit for global)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_species",
            "description": "List all species with their available capabilities (expression, motifs, traits, etc).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_provenance",
            "description": "Get data provenance manifest: version, methods, data sources with DOIs.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_citations",
            "description": "Export BibTeX citations for all atlas data sources.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_centrality",
            "description": "Compute centrality metrics (degree, betweenness, closeness, eigenvector) for genes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species to analyze"},
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs (alternative to species)"},
                    "metric": {"type": "string", "enum": ["degree", "in_degree", "out_degree", "betweenness", "closeness", "eigenvector"], "description": "Centrality metric (default: degree)"},
                    "top": {"type": "integer", "description": "Max results (default 50)"},
                    "min_confidence": {"type": "number", "description": "Min edge confidence"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_dsrna",
            "description": "Design or analyze dsRNA for RNAi gene silencing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_gene": {"type": "string", "description": "Gene ID to design dsRNA for"},
                    "sequence": {"type": "string", "description": "dsRNA sequence to analyze"},
                    "species": {"type": "string", "description": "Species name"},
                    "k": {"type": "integer", "description": "siRNA k-mer length (default 21)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_dsrna_screen",
            "description": "Batch dsRNA designability screen across a gene set. Ranks genes by off-target burden.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "species": {"type": "string", "description": "Species name"},
                    "k": {"type": "integer", "description": "siRNA k-mer length (default 21)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_network_patterns",
            "description": "Detect structural motifs: feed-forward loops, autoregulation, bi-fan patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species to search"},
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs to search within"},
                    "types": {"type": "string", "description": "Pattern types: ffl,autoregulation,bifan (default: all)"},
                    "min_confidence": {"type": "number", "description": "Min edge confidence"},
                    "limit": {"type": "integer", "description": "Max patterns (default 100)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_export",
            "description": "Export regulatory edges with genomic coordinates in JSON or TSV.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "format": {"type": "string", "enum": ["json", "tsv"], "description": "Output format (default: json)"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_motif_query",
            "description": "Query TF binding motif hits in gene promoters. Given a gene, find what TFs may bind its promoter. Given a TF, find which genes it may regulate via motif evidence. Optionally cross-reference with known regulatory edges. Available for arabidopsis, tomato, petunia only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Target gene ID (find TFs that bind its promoter)"},
                    "tf_gene_id": {"type": "string", "description": "TF gene ID (find genes with its binding motif)"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_pvalue": {"type": "number", "description": "Max motif hit p-value (default 1e-4)"},
                    "include_edge_support": {"type": "boolean", "description": "Cross-reference with known regulatory edges"},
                    "top": {"type": "integer", "description": "Max results (default 100)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_modules",
            "description": "Detect co-regulated gene modules/communities in a species regulatory network using graph algorithms. Identifies hub TFs within each module.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species name"},
                    "algorithm": {"type": "string", "enum": ["leiden", "louvain", "infomap", "label_propagation"], "description": "Community detection algorithm (default: louvain)"},
                    "gene_id": {"type": "string", "description": "Find this gene's module specifically"},
                    "min_confidence": {"type": "number", "description": "Min edge confidence"},
                    "resolution": {"type": "number", "description": "Resolution parameter for leiden/louvain (default 0.01)"},
                    "top_modules": {"type": "integer", "description": "Max modules to return (default 20)"},
                },
                "required": ["species"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_diff_regulation",
            "description": "Compare TF regulatory activity between two groups of conditions/tissues. Identifies TFs whose targets show differential expression. Available for arabidopsis, tomato, petunia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species name"},
                    "tf_gene_id": {"type": "string", "description": "Specific TF to analyze (optional, default: all TFs)"},
                    "group_a": {"type": "string", "description": "Comma-separated tissue names for condition A"},
                    "group_b": {"type": "string", "description": "Comma-separated tissue names for condition B"},
                    "min_fold_change": {"type": "number", "description": "Min |log2FC| to report (default 1.0)"},
                    "top": {"type": "integer", "description": "Max TFs to return (default 50)"},
                },
                "required": ["species", "group_a", "group_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_inferred_edges",
            "description": "Query GRNBoost2/GENIE3-inferred regulatory edges from expression data. Returns predicted TF-target relationships ranked by importance score. These are computational predictions, not experimentally validated. Available for arabidopsis, tomato, petunia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species name"},
                    "gene_id": {"type": "string", "description": "Gene ID or symbol to query edges for"},
                    "direction": {"type": "string", "description": "Edge direction: regulators, targets, or both (default both)"},
                    "method": {"type": "string", "description": "Inference method: GRNBoost2, GENIE3, or omit for both"},
                    "min_importance": {"type": "number", "description": "Min importance score threshold (default 1.0)"},
                    "compare_curated": {"type": "boolean", "description": "Cross-reference with curated interactions (default false)"},
                    "top": {"type": "integer", "description": "Max edges to return (default 50)"},
                },
                "required": ["species"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_evidence_audit",
            "description": "Summarize what evidence layers support a gene or regulatory edge, including curated, inferred, motif, coexpression, pathway, and trait support.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["gene", "edge"], "description": "Audit a gene or a specific regulatory edge"},
                    "gene_id": {"type": "string", "description": "Gene ID when scope=gene"},
                    "source_id": {"type": "string", "description": "Source gene ID when scope=edge"},
                    "target_id": {"type": "string", "description": "Target gene ID when scope=edge"},
                    "species": {"type": "string", "description": "Species name"},
                    "depth": {"type": "integer", "description": "Context depth (default 1)"},
                },
                "required": ["scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_coverage_report",
            "description": "Report whether a species has the required and optional layers needed for a given analysis intent, with readiness score and missing layers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species name"},
                    "intent": {"type": "string", "enum": ["network", "expression", "motif", "perturbation", "orthology", "traits", "rnai", "experiment"], "description": "Analysis intent"},
                    "gene_id": {"type": "string", "description": "Optional gene ID for gene-specific context"},
                },
                "required": ["species", "intent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_candidate_triage",
            "description": "Rank a gene list for a research intent using evidence support, TF status, and species coverage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent (experiment, network, rnai, etc.)"},
                    "species": {"type": "string", "description": "Species name"},
                    "top": {"type": "integer", "description": "Maximum ranked candidates to return (default 10)"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_experiment_prioritization",
            "description": "Recommend the next analyses or experiments to run for one or more genes based on evidence support and species coverage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_recommendations": {"type": "integer", "description": "Maximum recommendations per candidate (default 5)"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_confidence_boundary",
            "description": "State what the current atlas evidence supports, does not support, and leaves ambiguous for a candidate gene set and analysis intent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to summarize"},
                    "max_experiments": {"type": "integer", "description": "Maximum experiment summaries"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_transferability",
            "description": "Assess whether a gene-level claim or candidate can be transferred from the source species to a target species, including ortholog support and caveats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Source gene ID"},
                    "target_species": {"type": "string", "description": "Target species"},
                    "intent": {"type": "string", "description": "Research intent"},
                },
                "required": ["gene_id", "target_species"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_minimal_validation",
            "description": "Turn a candidate set and analysis intent into the smallest defensible validation path, including first step, blockers, stop/go gates, and fallback path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to summarize"},
                    "max_experiments": {"type": "integer", "description": "Maximum experiment summaries"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_evidence_synthesis",
            "description": "Synthesize atlas-backed evidence for a gene or gene set into a paper-style summary with support, weak evidence, stored PMIDs, citations, and reporting caveats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to summarize"},
                    "max_experiments": {"type": "integer", "description": "Maximum experiment summaries"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_hypothesis_compare",
            "description": "Compare competing candidate genes for the same analysis intent and explain which hypothesis is currently best supported and what evidence would change the ranking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated candidate gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to compare"},
                    "max_experiments": {"type": "integer", "description": "Maximum experiment summaries"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_research_brief",
            "description": "Build a structured research brief for a gene list and analysis intent, combining candidate ranking, experiment recommendations, species readiness, and evidence snapshots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to include"},
                    "max_experiments": {"type": "integer", "description": "Maximum experiment recommendations"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_validation_plan",
            "description": "Build an execution-ready validation plan from a gene list and analysis intent, including ranked validation tracks, decision gates, blockers, and success criteria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to include"},
                    "max_experiments": {"type": "integer", "description": "Maximum experiment tracks"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_study_packet",
            "description": "Build a shareable study packet from a gene list and analysis intent, bundling the research brief, validation plan, collaborator handoff notes, and citation/provenance context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to include"},
                    "max_experiments": {"type": "integer", "description": "Maximum experiment tracks"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_study_report",
            "description": "Build a collaborator-facing study report from a gene list and analysis intent, turning the study packet into a structured narrative with summary, validation status, and citations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to include"},
                    "max_experiments": {"type": "integer", "description": "Maximum experiment tracks"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_dataset_import",
            "description": "Import a user gene list or simple CSV/TSV content into the atlas, mapping symbols/IDs onto atlas genes and reporting ambiguous or unmapped rows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Inline gene list or CSV/TSV content"},
                    "species": {"type": "string", "description": "Optional species hint"},
                    "filename": {"type": "string", "description": "Optional source filename label"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_user_gene_set_analysis",
            "description": "Run a first-pass atlas workflow over a user-provided gene set: import/mapping summary, enrichment, upstream regulators, candidate triage, and optional subgraph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated atlas gene IDs or symbols"},
                    "content": {"type": "string", "description": "Inline gene list or CSV/TSV content"},
                    "species": {"type": "string", "description": "Optional species override"},
                    "filename": {"type": "string", "description": "Optional source filename label"},
                    "intent": {"type": "string", "description": "Analysis intent: experiment, network, rnai, traits"},
                    "top_terms": {"type": "integer", "description": "Maximum enrichment terms"},
                    "top_regulators": {"type": "integer", "description": "Maximum upstream regulators"},
                    "top_candidates": {"type": "integer", "description": "Maximum ranked candidates"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_differential_expression",
            "description": "Compare two atlas tissue/condition groups or analyze an imported DEG table to find genes with the largest expression changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species name for atlas-mode comparisons"},
                    "group_a": {"type": "string", "description": "Comma-separated tissues/conditions for group A"},
                    "group_b": {"type": "string", "description": "Comma-separated tissues/conditions for group B"},
                    "content": {"type": "string", "description": "Inline DEG table content"},
                    "filename": {"type": "string", "description": "Optional source filename label"},
                    "top": {"type": "integer", "description": "Maximum rows to return"},
                    "min_abs_log2fc": {"type": "number", "description": "Minimum absolute log2 fold change filter"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_experiment_optimizer",
            "description": "Re-rank follow-up experiments using feasibility constraints such as budget, time, and allowed assay classes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "budget_level": {"type": "string", "enum": ["low", "medium", "high"], "description": "Budget constraint"},
                    "timeline_days": {"type": "integer", "description": "Time constraint in days"},
                    "allowed_assays": {"type": "string", "description": "Comma-separated assay classes"},
                    "max_recommendations": {"type": "integer", "description": "Maximum ranked experiments"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_literature_review",
            "description": "Retrieve external literature relevant to a gene, edge, pathway, or phenotype and classify papers as support, contradiction, or mention.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["gene", "edge", "pathway", "phenotype"], "description": "Review scope"},
                    "gene_id": {"type": "string", "description": "Gene ID for gene scope"},
                    "source_id": {"type": "string", "description": "Source gene ID for edge scope"},
                    "target_id": {"type": "string", "description": "Target gene ID for edge scope"},
                    "query": {"type": "string", "description": "Free-text query for pathway or phenotype scope"},
                    "species": {"type": "string", "description": "Optional species hint"},
                    "years_back": {"type": "integer", "description": "Recency window in years"},
                    "max_results": {"type": "integer", "description": "Maximum papers to return"},
                },
                "required": ["scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_consensus_ranking",
            "description": "Rank candidate genes by a weighted consensus across atlas evidence layers and optional external literature support.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "top_n": {"type": "integer", "description": "Maximum candidates to return"},
                    "include_external": {"type": "boolean", "description": "Whether to incorporate external literature"},
                    "years_back": {"type": "integer", "description": "External literature recency window"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_counterfactual_analysis",
            "description": "Explain what evidence shifts would most likely overturn the current lead candidate or flip the ranking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "include_external": {"type": "boolean", "description": "Whether to incorporate external literature"},
                    "years_back": {"type": "integer", "description": "External literature recency window"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_variant_effect",
            "description": "Assess whether a promoter-region variant overlaps motif-supported regulatory sites for a gene.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Gene ID"},
                    "position": {"type": "integer", "description": "Genomic position"},
                    "assembly": {"type": "string", "description": "Optional assembly label"},
                    "window_type": {"type": "string", "description": "Window type, typically promoter"},
                    "ref": {"type": "string", "description": "Reference allele"},
                    "alt": {"type": "string", "description": "Alternate allele"},
                },
                "required": ["gene_id", "position"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_promoter_edit_prioritization",
            "description": "Prioritize motif-supported promoter sites or windows that are strategic editing targets for changing regulation of a gene.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_id": {"type": "string", "description": "Gene ID"},
                    "top": {"type": "integer", "description": "Maximum prioritized sites/windows"},
                },
                "required": ["gene_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_crispr_design",
            "description": "Suggest simple heuristic CRISPR guide RNAs from a provided DNA sequence or gene context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "DNA sequence to design guides from"},
                    "gene_id": {"type": "string", "description": "Gene ID if using atlas-linked context"},
                    "pam": {"type": "string", "description": "PAM sequence (default NGG)"},
                    "top": {"type": "integer", "description": "Maximum guides to return"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_primer_design",
            "description": "Suggest simple heuristic PCR/qPCR primer pairs from a provided DNA sequence or gene context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sequence": {"type": "string", "description": "DNA sequence to design primers from"},
                    "gene_id": {"type": "string", "description": "Gene ID if using atlas-linked context"},
                    "product_min": {"type": "integer", "description": "Minimum amplicon size"},
                    "product_max": {"type": "integer", "description": "Maximum amplicon size"},
                    "top": {"type": "integer", "description": "Maximum primer pairs to return"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_celltype_regulation",
            "description": "Report readiness and missing layers for cell-type or single-cell regulatory analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species name"},
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                },
                "required": ["species"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_trajectory_regulation",
            "description": "Report readiness and missing layers for time-series, pseudotime, or trajectory-resolved regulation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species name"},
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                },
                "required": ["species"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_combinatorial_perturbation",
            "description": "Rank pairwise or triple perturbation combinations by predicted downstream impact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs"},
                    "action": {"type": "string", "description": "Intervention action such as ko or oe"},
                    "combo_size": {"type": "integer", "description": "Combination size (2 or 3)"},
                    "species": {"type": "string", "description": "Species name"},
                    "top": {"type": "integer", "description": "Maximum combinations to return"},
                },
                "required": ["gene_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_species_onboarding_plan",
            "description": "Generate a staged plan for onboarding a new species into the atlas architecture, including required data layers and implementation steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species_name": {"type": "string", "description": "New species to onboard"},
                    "intended_capabilities": {"type": "string", "description": "Comma-separated capabilities to support"},
                },
                "required": ["species_name"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Map tool name -> skill directory name + arg translation
# ---------------------------------------------------------------------------

_TOOL_TO_SKILL = {
    "grn_motif_query": "grn-motif",
    "grn_modules": "grn-module",
    "grn_diff_regulation": "grn-diff-regulation",
    "grn_inferred_edges": "grn-infer",
}


def _tool_to_cli(tool_name: str, args: dict, http_url: str | None) -> list[str]:
    """Convert a tool call to CLI args for the corresponding skill's run.py."""
    skill_name = _TOOL_TO_SKILL.get(tool_name, tool_name.replace("_", "-"))
    script = SKILLS_DIR / skill_name / "scripts" / "run.py"
    cmd = [PYTHON, str(script)]
    if http_url:
        cmd += ["--http", http_url]

    arg_map = {
        "query": "--query", "species": "--species", "limit": "--limit",
        "gene_id": "--gene-id", "symbol": "--symbol", "direction": "--direction",
        "min_confidence": "--min-confidence", "source": "--source", "target": "--target",
        "max_depth": "--max-depth", "gene_ids": "--gene-ids", "type": "--type",
        "top": "--top", "min_r": "--min-r", "action": "--action", "depth": "--depth",
        "species_b": "--species-b", "target_gene": "--target-gene",
        "interventions": "--interventions", "tf_a": "--tf-a", "tf_b": "--tf-b",
        "metric": "--metric", "sequence": "--sequence", "k": "--k",
        "types": "--types", "format": "--format",
        "tf_gene_id": "--tf-gene-id", "max_pvalue": "--max-pvalue",
        "min_score": "--min-score", "include_edge_support": "--include-edge-support",
        "algorithm": "--algorithm", "resolution": "--resolution",
        "top_modules": "--top-modules",
        "group_a": "--group-a", "group_b": "--group-b",
        "min_fold_change": "--min-fold-change",
        "min_importance": "--min-importance",
        "compare_curated": "--compare-curated",
        "scope": "--scope", "source_id": "--source-id", "target_id": "--target-id",
        "intent": "--intent", "target_species": "--target-species",
        "max_recommendations": "--max-recommendations",
        "max_candidates": "--max-candidates", "max_experiments": "--max-experiments",
        "content": "--content", "filename": "--filename",
        "top_terms": "--top-terms", "top_regulators": "--top-regulators",
        "top_candidates": "--top-candidates",
        "group_a": "--group-a", "group_b": "--group-b",
        "min_abs_log2fc": "--min-abs-log2fc",
        "budget_level": "--budget-level", "timeline_days": "--timeline-days",
        "allowed_assays": "--allowed-assays",
        "years_back": "--years-back", "max_results": "--max-results",
        "top_n": "--top-n", "include_external": "--include-external",
        "position": "--position", "assembly": "--assembly", "window_type": "--window-type",
        "ref": "--ref", "alt": "--alt", "pam": "--pam",
        "product_min": "--product-min", "product_max": "--product-max",
        "combo_size": "--combo-size", "species_name": "--species-name",
        "intended_capabilities": "--intended-capabilities",
    }

    _BOOL_FLAGS = {"include_edge_support", "compare_curated", "include_external"}

    for key, val in args.items():
        if key in arg_map and val is not None:
            if key in _BOOL_FLAGS:
                if val:
                    cmd += [arg_map[key]]
            else:
                cmd += [arg_map[key], str(val)]

    return cmd


def execute_tool(tool_name: str, args: dict, http_url: str | None) -> str:
    """Run a skill and return its stdout (truncated to 4000 chars for context)."""
    cmd = _tool_to_cli(tool_name, args, http_url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(REPO_ROOT))
        if proc.returncode != 0:
            return json.dumps({"error": proc.stderr.strip()[-500:]})
        output = proc.stdout.strip()
        if len(output) > 4000:
            output = output[:4000] + "\n... [truncated]"
        return output
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "timeout"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Multi-step test questions with grading criteria
# ---------------------------------------------------------------------------

def _used(trace, *tool_names):
    """Check if any of the named tools were called."""
    return any(c["name"] in tool_names for c in trace["tool_calls"])

def _used_with(trace, tool_name, arg_key, arg_val):
    """Check if a tool was called with a specific arg value (substring match)."""
    return any(
        c["name"] == tool_name and arg_val.upper() in str(c["args"].get(arg_key, "")).upper()
        for c in trace["tool_calls"]
    )

def _n_skills(trace):
    """Count unique skills used."""
    return len(set(c["name"] for c in trace["tool_calls"]))

def _answer_has(trace, *terms):
    """Check if the final answer contains all terms (case-insensitive)."""
    raw = trace.get("final_answer") or ""
    ans = raw.lower() if isinstance(raw, str) else str(raw).lower()
    flat_terms = []
    for t in terms:
        if isinstance(t, (list, tuple, set)):
            flat_terms.extend(str(x) for x in t)
        else:
            flat_terms.append(str(t))
    return all(t.lower() in ans for t in flat_terms)

def _answer_has_any(trace, *terms):
    """Check if the final answer contains any of the terms."""
    raw = trace.get("final_answer") or ""
    ans = raw.lower() if isinstance(raw, str) else str(raw).lower()
    flat_terms = []
    for t in terms:
        if isinstance(t, (list, tuple, set)):
            flat_terms.extend(str(x) for x in t)
        else:
            flat_terms.append(str(t))
    return any(t.lower() in ans for t in flat_terms)

def _answer_has_number(trace):
    """Check if the final answer contains at least one number."""
    return any(ch.isdigit() for ch in trace["final_answer"])


QUESTIONS = [
    # =================================================================
    # Category 1: Network intersection / shared regulators (2 skills)
    # =================================================================
    {
        "question": (
            "What transcription factors regulate both TP53 and MYC in humans? "
            "For each shared regulator, tell me whether it activates or represses each gene."
        ),
        "checks": [
            ("used network or subgraph", lambda t: _used(t, "grn_network", "grn_subgraph")),
            ("queried both TP53 and MYC", lambda t: (
                sum(1 for c in t["tool_calls"]
                    if c["name"] == "grn_network" and c["args"].get("gene_id") in ("TP53", "MYC")) >= 2
                or _used(t, "grn_subgraph")
            )),
            ("identifies shared regulators", lambda t:
                _answer_has_any(t, "shared", "common", "both", "overlap", "regulator", "TF")),
            ("provides activation/repression info", lambda t:
                _answer_has_any(t, "activat", "repress")),
        ],
    },

    # =================================================================
    # Category 2: RNAi experiment pipeline (3-4 skills)
    # =================================================================
    {
        "question": (
            "I want to silence HY5 in Arabidopsis using RNAi. "
            "First check if a dsRNA can be designed for it, then tell me what downstream genes "
            "would be affected if HY5 is knocked out, and what GO terms are enriched in those targets."
        ),
        "checks": [
            ("called dsRNA design", lambda t: _used(t, "grn_dsrna")),
            ("called perturbation or network for HY5", lambda t: any(
                c["name"] in ("grn_perturbation", "grn_network") and
                ("AT5G11260" in str(c["args"]) or "HY5" in str(c["args"]))
                for c in t["tool_calls"])),
            ("called enrichment", lambda t: _used(t, "grn_enrichment")),
            ("used >= 3 different skills", lambda t: _n_skills(t) >= 3),
        ],
    },

    # =================================================================
    # Category 3: Regulon comparison + enrichment (2-3 skills)
    # =================================================================
    {
        "question": (
            "Compare the regulatory programs of TP53 and NFKB1. "
            "How many targets do they share? What pathways are enriched in the shared targets?"
        ),
        "checks": [
            ("used regulon_compare or network for both", lambda t: (
                _used(t, "grn_regulon_compare")
                or sum(1 for c in t["tool_calls"]
                       if c["name"] == "grn_network" and c["args"].get("gene_id") in ("TP53", "NFKB1")) >= 2
            )),
            ("called enrichment", lambda t: _used(t, "grn_enrichment")),
            ("mentions shared target count", lambda t: _answer_has_number(t)),
        ],
    },

    # =================================================================
    # Category 4: Cross-species conservation (2-3 skills)
    # =================================================================
    {
        "question": (
            "Is the TP53→BAX regulatory relationship conserved in mouse? "
            "Find the regulatory path from TP53 to BAX in humans, and check if a similar path exists in mouse."
        ),
        "checks": [
            ("used pathfinding", lambda t: _used(t, "grn_pathfinding")),
            ("checked conservation or orthology", lambda t:
                _used(t, "grn_conservation", "grn_orthology")),
            ("mentions conservation, ortholog, or mouse", lambda t:
                _answer_has_any(t, "conserv", "confidence", "ortholog", "mouse", "mus musculus")),
        ],
    },

    # =================================================================
    # Category 5: Discovery chain — species → centrality → coexpression (3 skills)
    # =================================================================
    {
        "question": (
            "Which species in the atlas have expression data available? "
            "For one of those species, find the top hub transcription factor by out-degree centrality "
            "and tell me its top 5 co-expressed genes."
        ),
        "checks": [
            ("checked species", lambda t: _used(t, "grn_species")),
            ("used centrality", lambda t: _used(t, "grn_centrality")),
            ("used coexpression", lambda t: _used(t, "grn_coexpression")),
            ("used >= 3 skills", lambda t: _n_skills(t) >= 3),
        ],
    },

    # =================================================================
    # Category 6: Upstream regulator analysis + validation (2-3 skills)
    # =================================================================
    {
        "question": (
            "I have a set of differentially expressed genes: BAX, BCL2, CDKN1A, MDM2, GADD45A. "
            "Identify which transcription factors likely regulate this set, then show me "
            "the regulatory paths from the top predicted TF to each of these genes."
        ),
        "checks": [
            ("used upstream analysis", lambda t: _used(t, "grn_upstream")),
            ("used pathfinding to validate", lambda t: _used(t, "grn_pathfinding")),
            ("mentions TP53 as top regulator", lambda t: "TP53" in t["final_answer"]),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },

    # =================================================================
    # Category 7: Network patterns + subgraph (2-3 skills)
    # =================================================================
    {
        "question": (
            "Find feed-forward loops involving TP53, MYC, and E2F1 in the human network. "
            "Then extract the full regulatory subgraph among these three genes and tell me "
            "how many edges connect them."
        ),
        "checks": [
            ("used network_patterns", lambda t: _used(t, "grn_network_patterns")),
            ("used subgraph or network", lambda t: _used(t, "grn_subgraph", "grn_network")),
            ("mentions edge count", lambda t: _answer_has_number(t)),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },

    # =================================================================
    # Category 8: Gene lookup → perturbation → enrichment (3 skills)
    # =================================================================
    {
        "question": (
            "What would happen if MYC is knocked out? "
            "Predict the downstream effects, then run GO enrichment on the affected genes "
            "to understand which biological processes would be disrupted."
        ),
        "checks": [
            ("used perturbation for MYC", lambda t: any(
                c["name"] == "grn_perturbation" and "MYC" in str(c["args"])
                for c in t["tool_calls"])),
            ("called GO enrichment", lambda t: any(
                c["name"] == "grn_enrichment" and c["args"].get("type") == "go"
                for c in t["tool_calls"])),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
            ("answer mentions biological processes", lambda t:
                _answer_has_any(t, "process", "pathway", "apoptosis", "cell cycle", "proliferat")),
        ],
    },

    # =================================================================
    # Category 9: Cross-species RNAi screen (3-4 skills)
    # =================================================================
    {
        "question": (
            "Screen HY5 (AT5G11260) and PIF4 (AT2G43010) in Arabidopsis for dsRNA "
            "designability. Explicitly tell me which gene has better specificity or lower "
            "off-target burden, then predict the downstream perturbation effects of "
            "silencing that winner."
        ),
        "checks": [
            ("used dsrna_screen or dsrna", lambda t: _used(t, "grn_dsrna_screen", "grn_dsrna")),
            ("used perturbation", lambda t: _used(t, "grn_perturbation")),
            ("mentions specificity or off-target", lambda t:
                _answer_has_any(t, "specific", "off-target", "off_target")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "Screen ABF1 (AT1G49720), ABF2 (AT1G45249), and PIF4 (AT2G43010) in "
            "Arabidopsis for dsRNA designability. Tell me which target has the best "
            "specificity and the lowest off-target burden."
        ),
        "checks": [
            ("used dsrna_screen", lambda t: _used(t, "grn_dsrna_screen")),
            ("mentions specificity or off-target", lambda t:
                _answer_has_any(t, "specific", "off-target", "off_target", "burden")),
            ("used 1 or more skills", lambda t: _n_skills(t) >= 1),
        ],
    },
    {
        "question": (
            "Screen HY5 (AT5G11260) and PIF4 (AT2G43010) in Arabidopsis for dsRNA "
            "designability. Then, for the more specific target, predict downstream "
            "perturbation effects and summarize which biological processes are enriched."
        ),
        "checks": [
            ("used dsrna_screen or dsrna", lambda t: _used(t, "grn_dsrna_screen", "grn_dsrna")),
            ("used perturbation", lambda t: _used(t, "grn_perturbation")),
            ("used enrichment", lambda t: _used(t, "grn_enrichment")),
            ("mentions specificity or off-target", lambda t:
                _answer_has_any(t, "specific", "off-target", "off_target")),
            ("used >= 3 skills", lambda t: _n_skills(t) >= 3),
        ],
    },

    # =================================================================
    # Category 10: Cascade modeling (2-3 skills)
    # =================================================================
    {
        "question": (
            "If SIRT1 activity increases 1.5-fold, predict the cascade effect "
            "on TP53 and its downstream targets. Then find what pathways are enriched "
            "among the cascade-affected genes."
        ),
        "checks": [
            ("used cascade", lambda t: _used(t, "grn_cascade")),
            ("called enrichment", lambda t: _used(t, "grn_enrichment")),
            ("mentions affected gene count", lambda t: _answer_has_number(t)),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },

    # =================================================================
    # Category 11: Ortholog comparison pipeline (3 skills)
    # =================================================================
    {
        "question": (
            "Find the mouse ortholog of human E2F1. Compare the regulatory networks "
            "of E2F1 in human vs its mouse ortholog — how many regulators and targets "
            "does each have? Are the regulatory edges conserved?"
        ),
        "checks": [
            ("used orthology", lambda t: _used(t, "grn_orthology")),
            ("used network or conservation", lambda t:
                _used(t, "grn_network", "grn_conservation")),
            ("mentions regulator/target counts", lambda t: _answer_has_number(t)),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },

    # =================================================================
    # Category 12: Database orientation + focused analysis (3 skills)
    # =================================================================
    {
        "question": (
            "How many genes and interactions are in the GRN Atlas? "
            "Which species has the most transcription factors? "
            "For that species, who are the top 3 TFs by betweenness centrality?"
        ),
        "checks": [
            ("used stats", lambda t: _used(t, "grn_stats")),
            ("used centrality", lambda t: _used(t, "grn_centrality")),
            ("mentions betweenness", lambda t: _answer_has(t, "betweenness")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },

    # =================================================================
    # Category 13: Expression-guided network analysis (3 skills)
    # =================================================================
    {
        "question": (
            "Get the expression profile of ABF1 (AT1G49720) in Arabidopsis. "
            "Find its top 5 co-expressed partners, then check which of those "
            "co-expressed genes are also direct regulatory targets of ABF1."
        ),
        "checks": [
            ("used expression", lambda t: _used(t, "grn_expression")),
            ("used coexpression", lambda t: _used(t, "grn_coexpression")),
            ("used network", lambda t: _used(t, "grn_network", "grn_regulon")),
            ("used >= 3 skills", lambda t: _n_skills(t) >= 3),
        ],
    },

    # =================================================================
    # Category 14: Regulon comparison across TF families (2-3 skills)
    # =================================================================
    {
        "question": (
            "Compare the regulons of TP53 and E2F1 at depth 1. "
            "What is their Jaccard similarity? "
            "Run pathway enrichment on their overlapping targets."
        ),
        "checks": [
            ("used regulon_compare", lambda t: _used(t, "grn_regulon_compare")),
            ("called enrichment on overlap", lambda t: _used(t, "grn_enrichment")),
            ("mentions Jaccard or overlap", lambda t:
                _answer_has_any(t, "jaccard", "overlap")),
            ("mentions number", lambda t: _answer_has_number(t)),
        ],
    },

    # =================================================================
    # Category 15: Provenance-aware analysis (2 skills)
    # =================================================================
    {
        "question": (
            "What data sources were used to build the GRN Atlas, and what methods "
            "were used for edge inference? Then show me the global database statistics "
            "so I can cite the atlas properly in a paper."
        ),
        "checks": [
            ("used provenance", lambda t: _used(t, "grn_provenance")),
            ("used stats or citations", lambda t: _used(t, "grn_stats", "grn_citations")),
            ("mentions data source", lambda t:
                _answer_has_any(t, "TRRUST", "PlantRegMap", "JASPAR", "source")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },

    # =================================================================
    # Category 16: Export pipeline for downstream tools (3 skills)
    # =================================================================
    {
        "question": (
            "I need to build a Cytoscape network of the TP53 signaling neighborhood. "
            "Get all regulators and targets of TP53, then export the regulatory edges "
            "among TP53 and its top 5 regulators in JSON format with genomic coordinates."
        ),
        "checks": [
            ("used network for TP53", lambda t: _used_with(t, "grn_network", "gene_id", "TP53")),
            ("used export", lambda t: _used(t, "grn_export")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },

    # =================================================================
    # Category 17: Multi-perturbation + comparison (2-3 skills)
    # =================================================================
    {
        "question": (
            "Compare the predicted effects of knocking out TP53 alone versus knocking out "
            "both TP53 and MYC simultaneously. Are there genes affected by the double "
            "knockout that aren't affected by TP53 KO alone?"
        ),
        "checks": [
            ("used single perturbation", lambda t: any(
                c["name"] == "grn_perturbation" and "TP53" in str(c["args"])
                and "MYC" not in str(c["args"])
                for c in t["tool_calls"])),
            ("used multi perturbation", lambda t: any(
                c["name"] == "grn_perturbation" and "TP53" in str(c["args"])
                and "MYC" in str(c["args"])
                for c in t["tool_calls"])),
            ("compares the two", lambda t: _answer_has_number(t)),
        ],
    },

    # =================================================================
    # Category 18: Arabidopsis cross-species regulatory conservation (3 skills)
    # =================================================================
    {
        "question": (
            "Check whether HY5 (AT5G11260) has an ortholog in tomato. "
            "If so, compare the regulatory edges of HY5 between Arabidopsis and tomato. "
            "How conserved is its regulatory program?"
        ),
        "checks": [
            ("used orthology for HY5", lambda t: any(
                c["name"] == "grn_orthology" and "AT5G11260" in str(c["args"])
                for c in t["tool_calls"])),
            ("used conservation or network", lambda t:
                _used(t, "grn_conservation", "grn_network")),
            ("mentions tomato", lambda t: _answer_has(t, "tomato")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },

    # =================================================================
    # Category 19: Autoregulation + centrality analysis (2-3 skills)
    # =================================================================
    {
        "question": (
            "Which human transcription factors autoregulate themselves? "
            "Of those autoregulators, which have the highest out-degree centrality — "
            "i.e., which autoregulating TFs are also major hub regulators?"
        ),
        "checks": [
            ("used network_patterns for autoregulation", lambda t: any(
                c["name"] == "grn_network_patterns"
                and "autoregulation" in str(c["args"]).lower()
                for c in t["tool_calls"])),
            ("used centrality", lambda t: _used(t, "grn_centrality")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },

    # =================================================================
    # Category 20: Full experimental design pipeline (4+ skills)
    # =================================================================
    {
        "question": (
            "I'm planning an RNAi experiment in Arabidopsis to study ABA signaling. "
            "Screen ABF1 (AT1G49720), ABF2 (AT1G45249), and PIF4 (AT2G43010) for "
            "dsRNA designability. For the most specific target, predict the perturbation "
            "effects of silencing it, and run GO enrichment on the affected downstream genes."
        ),
        "checks": [
            ("used dsrna_screen or dsrna", lambda t: _used(t, "grn_dsrna_screen", "grn_dsrna")),
            ("used perturbation or enrichment", lambda t:
                _used(t, "grn_perturbation", "grn_enrichment")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    # =================================================================
    # Category 11: Network inference + validation (grn-infer chains)
    # =================================================================
    {
        "question": (
            "Find inferred regulatory edges for HY5 (AT5G11260) in Arabidopsis using "
            "GRNBoost2. For the top predicted regulators, check whether they also appear "
            "in the curated network as known regulators of HY5."
        ),
        "checks": [
            ("used inferred edges", lambda t: _used(t, "grn_inferred_edges")),
            ("used network", lambda t: _used(t, "grn_network")),
            ("mentioned HY5 or AT5G11260", lambda t: _answer_has_any(t, ["HY5", "AT5G11260"])),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "Compare GRNBoost2 and GENIE3 predictions for top regulators of AT3G24650 "
            "in Arabidopsis. Which TFs are predicted by both methods? For the TFs predicted "
            "by both, look up their gene information."
        ),
        "checks": [
            ("used inferred edges", lambda t: _used(t, "grn_inferred_edges")),
            ("queried both methods", lambda t:
                {str(c["args"].get("method", "")).upper() for c in t["tool_calls"]
                 if c["name"] == "grn_inferred_edges" and c["args"].get("method")} >= {"GRNBOOST2", "GENIE3"}
                or _answer_has_any(t, "GRNBoost2", "GENIE3", "both")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "What genes does GRNBoost2 predict are regulated by PIL5 (AT2G20180) in "
            "Arabidopsis? Run GO enrichment on those predicted targets to see what "
            "biological processes PIL5 might be controlling."
        ),
        "checks": [
            ("used inferred edges", lambda t: _used(t, "grn_inferred_edges")),
            ("used enrichment", lambda t: _used(t, "grn_enrichment")),
            ("mentioned PIL5 or AT2G20180", lambda t: _answer_has_any(t, ["PIL5", "AT2G20180"])),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "For Arabidopsis, find the top inferred regulatory edges with curated support. "
            "Then check whether those TFs show differential regulation between root and "
            "inflorescence tissues."
        ),
        "checks": [
            ("used inferred edges", lambda t: _used(t, "grn_inferred_edges")),
            ("used diff regulation", lambda t: _used(t, "grn_diff_regulation")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "Identify predicted regulatory modules in Arabidopsis using community detection. "
            "For the largest module, find GRNBoost2-inferred edges within that module. "
            "How many of those inferred edges have curated support?"
        ),
        "checks": [
            ("used modules", lambda t: _used(t, "grn_modules")),
            ("used inferred edges", lambda t: _used(t, "grn_inferred_edges")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "For TP53, BAX, and MDM2 in a human experiment follow-up, rank the candidates, "
            "recommend the next experiments, and then build a structured research brief."
        ),
        "checks": [
            ("used candidate triage", lambda t: _used(t, "grn_candidate_triage")),
            ("used experiment prioritization", lambda t: _used(t, "grn_experiment_prioritization")),
            ("used research brief", lambda t: _used(t, "grn_research_brief")),
            ("used >= 3 skills", lambda t: _n_skills(t) >= 3),
        ],
    },
    {
        "question": (
            "Before I act on TP53 and BAX in a human experiment setting, audit what supports the "
            "TP53 to BAX edge, state the confidence boundary for the candidate set, and then "
            "produce a writing-ready evidence synthesis."
        ),
        "checks": [
            ("used evidence audit", lambda t: _used(t, "grn_evidence_audit")),
            ("used confidence boundary", lambda t: _used(t, "grn_confidence_boundary")),
            ("used evidence synthesis", lambda t: _used(t, "grn_evidence_synthesis")),
            ("used >= 3 skills", lambda t: _n_skills(t) >= 3),
        ],
    },
    {
        "question": (
            "I want to run RNAi on the petunia gene Peaxi162Scf00118g00310. "
            "First check whether petunia has the required atlas coverage for RNAi, then build "
            "a validation plan, and finally reduce that to the minimal next move."
        ),
        "checks": [
            ("used coverage report", lambda t: _used(t, "grn_coverage_report")),
            ("used validation plan", lambda t: _used(t, "grn_validation_plan")),
            ("used minimal validation", lambda t: _used(t, "grn_minimal_validation")),
            ("used >= 3 skills", lambda t: _n_skills(t) >= 3),
        ],
    },
    {
        "question": (
            "Compare TP53, BAX, and MDM2 as competing experiment hypotheses in human. "
            "First triage them, then compare the competing hypotheses and explain what evidence "
            "would change the current winner."
        ),
        "checks": [
            ("used candidate triage", lambda t: _used(t, "grn_candidate_triage")),
            ("used hypothesis compare", lambda t: _used(t, "grn_hypothesis_compare")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "Assess whether TP53-driven network conclusions transfer from human to mouse. "
            "Use ortholog context if needed, run a transferability assessment, and explain the caveats."
        ),
        "checks": [
            ("used orthology or conservation context", lambda t: _used(t, "grn_orthology", "grn_conservation")),
            ("used transferability", lambda t: _used(t, "grn_transferability")),
            ("mentions caveat or transfer", lambda t: _answer_has_any(t, "caveat", "transfer", "ortholog", "mouse")),
        ],
    },
    {
        "question": (
            "Prepare a collaborator handoff for TP53, BAX, and MDM2 in a human experiment follow-up. "
            "Build the research brief, convert it into a validation plan, then generate both a study "
            "packet and a study report."
        ),
        "checks": [
            ("used study packet", lambda t: _used(t, "grn_study_packet")),
            ("used study report", lambda t: _used(t, "grn_study_report")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "Find the Arabidopsis gene HY5 by searching the atlas, then retrieve its detailed record "
            "and tell me its locus ID and whether it is a transcription factor."
        ),
        "checks": [
            ("used gene search", lambda t: _used(t, "grn_gene_search")),
            ("used gene info", lambda t: _used(t, "grn_gene_info")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "For Arabidopsis HY5 (AT5G11260), find which transcription factor motifs are present in its "
            "promoter and whether any of those motif hits have known edge support."
        ),
        "checks": [
            ("used motif query", lambda t: _used(t, "grn_motif_query")),
            ("used >= 1 skills", lambda t: _n_skills(t) >= 1),
            ("mentions motif or promoter", lambda t: _answer_has_any(t, "motif", "promoter", "binding")),
        ],
    },
    {
        "question": (
            "I have this human hit list: TP53, BAX, and MDM2. Import the list into the atlas, "
            "then run a first-pass gene-set analysis and tell me the top ranked candidate and "
            "the top predicted upstream regulator."
        ),
        "checks": [
            ("used dataset import", lambda t: _used(t, "grn_dataset_import")),
            ("used user gene-set analysis", lambda t: _used(t, "grn_user_gene_set_analysis")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
            ("mentions TP53 or upstream", lambda t: _answer_has_any(t, "TP53", "upstream", "regulator")),
        ],
    },
    {
        "question": (
            "Compare root versus inflorescence in Arabidopsis to find strongly shifted genes. "
            "Then, assuming a low budget and only 3 days, rank the most feasible follow-up "
            "experiments for the top candidates."
        ),
        "checks": [
            ("used differential expression", lambda t: _used(t, "grn_differential_expression")),
            ("used experiment optimizer", lambda t: _used(t, "grn_experiment_optimizer")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
            ("mentions low budget or 3 days", lambda t: _answer_has_any(t, "low", "3", "budget", "day")),
        ],
    },
    {
        "question": (
            "For TP53, BAX, and MDM2 in a human experiment follow-up, look up recent external literature "
            "for TP53 and the TP53 to BAX relationship, then build a consensus ranking with external evidence "
            "and explain what would overturn the current winner."
        ),
        "checks": [
            ("used literature review", lambda t: _used(t, "grn_literature_review")),
            ("used consensus ranking", lambda t: _used(t, "grn_consensus_ranking")),
            ("used counterfactual analysis", lambda t: _used(t, "grn_counterfactual_analysis")),
            ("used >= 3 skills", lambda t: _n_skills(t) >= 3),
        ],
    },
    {
        "question": (
            "For HY5 (AT5G11260), assess whether a promoter variant at position 1900 with A to G overlaps "
            "a motif-supported regulatory site. Then prioritize the best promoter edit targets and suggest "
            "both CRISPR guides and primer pairs for follow-up."
        ),
        "checks": [
            ("used variant effect", lambda t: _used(t, "grn_variant_effect")),
            ("used promoter prioritization", lambda t: _used(t, "grn_promoter_edit_prioritization")),
            ("used crispr design", lambda t: _used(t, "grn_crispr_design")),
            ("used primer design", lambda t: _used(t, "grn_primer_design")),
            ("used >= 4 skills", lambda t: _n_skills(t) >= 4),
        ],
    },
    {
        "question": (
            "For TP53 and BAX in human, tell me honestly whether cell-type and trajectory-level regulatory "
            "analysis are supported today, and what layers are missing. Then tell me what it would take to "
            "onboard wheat into the atlas with network, expression, motif, orthology, and RNAi support."
        ),
        "checks": [
            ("used celltype readiness", lambda t: _used(t, "grn_celltype_regulation")),
            ("used trajectory readiness", lambda t: _used(t, "grn_trajectory_regulation")),
            ("used species onboarding", lambda t: _used(t, "grn_species_onboarding_plan")),
            ("used >= 3 skills", lambda t: _n_skills(t) >= 3),
        ],
    },
    {
        "question": (
            "Among TP53, BAX, and MDM2 in human, rank the pairwise knockout combinations by predicted downstream "
            "impact. Then compare that combination-level result against the single-gene consensus ranking."
        ),
        "checks": [
            ("used combinatorial perturbation", lambda t: _used(t, "grn_combinatorial_perturbation")),
            ("used consensus ranking", lambda t: _used(t, "grn_consensus_ranking")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
]


# ---------------------------------------------------------------------------
# OpenRouter chat completion
# ---------------------------------------------------------------------------

def chat_completion(messages: list, model: str, api_key: str) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": 4096,
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


SYSTEM_PROMPT = """\
You are a bioinformatics research assistant with access to the GRN Atlas \
gene regulatory network database. You have tools to search genes, explore \
regulatory networks, run enrichment analyses, predict perturbation effects, \
design dsRNA, and more.

When answering questions:
1. Use the available tools to gather data — don't guess.
2. You may call multiple tools in sequence to build up a complete answer.
3. Synthesize the tool results into a clear, data-backed answer.
4. Cite specific numbers from the tool outputs.

Key gene IDs to know:
- Human genes use symbols directly: TP53, MYC, BAX, NFKB1, E2F1, etc.
- Arabidopsis genes use AGI locus IDs: AT5G11260 (HY5), AT1G49720 (ABF1), AT2G43010 (PIF4)
- Tomato genes use Solyc IDs.
"""


def run_question(question: str, model: str, api_key: str, http_url: str | None,
                 verbose: bool = False) -> dict:
    """Run a single multi-step question through the LLM agent loop."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    tool_calls_log = []

    for round_num in range(MAX_TOOL_ROUNDS):
        if verbose:
            print(f"  [round {round_num + 1}]")

        try:
            response = chat_completion(messages, model, api_key)
        except Exception as e:
            return {
                "tool_calls": tool_calls_log,
                "final_answer": f"[API ERROR: {e}]",
                "rounds": round_num + 1,
                "error": str(e),
            }

        if "choices" not in response:
            err_msg = response.get("error", {})
            if isinstance(err_msg, dict):
                err_msg = err_msg.get("message", str(response))
            if verbose:
                print(f"    [API error: {str(err_msg)[:200]}]")
            return {
                "tool_calls": tool_calls_log,
                "final_answer": f"[API ERROR: {err_msg}]",
                "rounds": round_num + 1,
                "error": str(err_msg),
            }

        choice = response["choices"][0]
        msg = choice["message"]
        messages.append(msg)

        # Check for tool calls
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                except json.JSONDecodeError:
                    args = {}

                if verbose:
                    print(f"    → {name}({json.dumps(args, indent=None)[:120]})")

                tool_calls_log.append({"name": name, "args": args})
                result = execute_tool(name, args, http_url)

                if verbose and len(result) < 300:
                    print(f"    ← {result[:200]}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
        else:
            # No tool calls — model is done
            return {
                "tool_calls": tool_calls_log,
                "final_answer": msg.get("content", ""),
                "rounds": round_num + 1,
                "error": None,
            }

        if choice.get("finish_reason") == "stop" and not msg.get("tool_calls"):
            return {
                "tool_calls": tool_calls_log,
                "final_answer": msg.get("content", ""),
                "rounds": round_num + 1,
                "error": None,
            }

    return {
        "tool_calls": tool_calls_log,
        "final_answer": messages[-1].get("content", "[max rounds reached]"),
        "rounds": MAX_TOOL_ROUNDS,
        "error": "max_rounds",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LLM skill-orchestration test")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--http", default=None, help="GRN Atlas server URL")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--question", type=int, default=None, help="Run only question N (1-indexed)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    questions = QUESTIONS
    if args.question is not None:
        idx = args.question - 1
        if idx < 0 or idx >= len(QUESTIONS):
            print(f"ERROR: --question must be 1-{len(QUESTIONS)}", file=sys.stderr)
            sys.exit(1)
        questions = [QUESTIONS[idx]]

    print(f"Model: {args.model}")
    print(f"Questions: {len(questions)}")
    print(f"Tools: {len(TOOLS)}")
    print()

    all_results = []
    for i, q in enumerate(questions):
        q_num = (args.question or i + 1)
        print(f"Q{q_num}: {q['question'][:80]}...")
        t0 = time.time()
        trace = run_question(q["question"], args.model, api_key, args.http, args.verbose)
        elapsed = time.time() - t0

        check_results = []
        for desc, pred in q["checks"]:
            try:
                passed = pred(trace)
            except Exception as e:
                passed = False
                desc += f" [exception: {e}]"
            check_results.append({"check": desc, "pass": passed})

        grade = "PASS" if all(c["pass"] for c in check_results) else "FAIL"
        result = {
            "question": q["question"],
            "grade": grade,
            "checks": check_results,
            "tool_calls_count": len(trace["tool_calls"]),
            "unique_skills": len(set(c["name"] for c in trace["tool_calls"])),
            "rounds": trace["rounds"],
            "elapsed_s": round(elapsed, 1),
            "error": trace["error"],
        }
        all_results.append(result)

        status = "✓" if grade == "PASS" else "✗"
        print(f"  {status} {grade}  ({len(trace['tool_calls'])} calls, "
              f"{result['unique_skills']} skills, {elapsed:.1f}s)")
        for c in check_results:
            mark = "✓" if c["pass"] else "✗"
            print(f"    {mark} {c['check']}")

        if args.verbose and trace["final_answer"]:
            print(f"\n  Answer: {trace['final_answer'][:500]}\n")

        print()

    # Summary
    passed = sum(1 for r in all_results if r["grade"] == "PASS")
    total = len(all_results)
    print(f"{'=' * 60}")
    print(f"Results: {passed}/{total} PASS")
    print(f"Total tool calls: {sum(r['tool_calls_count'] for r in all_results)}")
    print(f"Avg skills/question: {sum(r['unique_skills'] for r in all_results) / total:.1f}")

    # Save results
    out_path = SKILLS_DIR / "_test_results_llm.json"
    with open(out_path, "w") as f:
        json.dump({"model": args.model, "results": all_results}, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
