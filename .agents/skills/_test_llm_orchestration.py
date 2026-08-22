#!/usr/bin/env python3
"""
LLM skill-orchestration test harness for GRN Atlas.

Sends complex multi-step biology questions to an LLM,
exposes all GRN Atlas skills as callable tools, lets the model call them
iteratively, and grades the final synthesized answer.

Usage:
    export OPENROUTER_API_KEY=sk-or-...
    export OPENAI_API_KEY=sk-...
    backend/venv/bin/python .agents/skills/_test_llm_orchestration.py

Options:
    --model MODEL_ID    Model id (default: nvidia/nemotron-3-ultra-550b-a55b:free)
    --provider NAME     auto | openrouter | openai
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
import urllib.error
import urllib.request
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
PYTHON = str(REPO_ROOT / "backend" / "venv" / "bin" / "python")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
MAX_TOOL_ROUNDS = 10
API_RETRIES = 6
API_BACKOFF_S = 5
API_TIMEOUT_S = 180

try:
    from _test_llm_tool_extensions import EXTRA_ARG_MAP, EXTRA_TOOLS, EXTRA_TOOL_TO_SKILL
except Exception:
    EXTRA_TOOLS = []
    EXTRA_TOOL_TO_SKILL = {}
    EXTRA_ARG_MAP = {}

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "grn_atlas_overview",
            "description": "Get a compact overview of the GRN Atlas: high-level supported species coverage, major analysis types, and example workflows. Not for exact species capability details, provenance manifests, or citation export.",
            "parameters": {
                "type": "object",
                "properties": {}
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_gene_search",
            "description": "Search for genes by exact symbol, alias, name, or keyword. Use this first when the gene identifier is unknown, ambiguous, or the user asks to find or search for a gene such as 'find TP53 in human' or 'search MYC limit 1'. Returns matching genes with id, symbol, name, species, gene_type, is_tf.",
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
            "description": "Get detailed info about a gene by ID or symbol. Returns id, symbol, name, species, gene_type, is_tf, synonyms. Use after search, orthology, regulon, or inferred-edge comparison when the user asks to look up shared TFs or inspect overlapping hits.",
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
            "description": "Get the immediate regulators and/or targets of one gene with confidence scores. Use this for prompts like 'downstream targets of ABF1' or 'all regulatory connections for NFKB1'. Prefer this over grn_regulon when the user wants only the local neighborhood rather than the full expanded regulon.",
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
            "description": "Find regulatory paths from a source gene to a target gene through intermediate regulators or targets. Use this for prompts like 'path from TP53 to BAX', 'direct path TP53 to TERT', or source→target connectivity questions. Prefer this over grn_network when both endpoints are specified.",
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
            "name": "grn_shared_regulators",
            "description": "Find transcription factors that regulate two or more target genes in common, with per-target direction and confidence. Use this first for questions like 'what regulates both TP53 and MYC', 'shared regulators', or 'common upstream TFs'. Prefer this over separate grn_network calls when the user wants the overlap.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated target gene IDs"},
                    "species": {"type": "string", "description": "Species name"},
                    "min_confidence": {"type": "number", "description": "Min edge confidence (default 0.3)"},
                    "top": {"type": "integer", "description": "Max shared regulators to return (default 25)"}
                },
                "required": ["gene_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grn_enrichment",
            "description": "Run overrepresentation analysis (GO, pathway, trait, motif) on a gene set. Use this when the user asks what GO terms, pathways, functions, motifs, or GWAS traits are enriched, including single-gene trait prompts like 'GWAS traits for TP53' or 'is TP53 associated with cancer in GWAS data?'. Prefer this over grn_gene_info or grn_evidence_audit when the task is explicit trait/GWAS enrichment.",
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
            "description": "Get the expression profile of a single gene across samples or tissues, returning TPM per sample. Use this for straightforward prompts like 'expression of PIF4 in arabidopsis' or 'show ABF2 expression'.",
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
            "description": "Find top co-expressed genes by Pearson correlation. Use this after you have identified a specific gene and the user asks for co-expressed partners, especially requests like 'top 5 co-expressed genes'.",
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
            "description": "Predict downstream effects of knocking out or overexpressing a gene. Use this after dsRNA/RNAi design when the user asks what genes would change if the target is silenced or knocked out. Pass the target in gene_id (or gene_ids for multi-intervention). Do not send a separate species argument; species is inferred from the gene ID or symbol resolution upstream.",
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
            "description": "Extract the induced regulatory subgraph for a gene set. Prefer this when the user gives 2 or more genes and asks for the edges or interactions among them.",
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
            "description": "Find cross-species orthologs with their regulatory networks. Use this when the question asks whether a gene or regulatory relationship carries over to another species such as mouse, tomato, or petunia.",
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
            "description": "Analyze conservation of regulatory edges between two species. Use this when the user asks whether a relationship or pathway is conserved across species and wants an explicit conservation judgment.",
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
            "description": "Predict how upstream interventions propagate through the network to affect a target gene. Use this when the user asks what changing one or more regulators would do to a downstream target, rather than asking for a generic perturbation outcome.",
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
            "description": "Extract the full regulon of a transcription factor (all direct+indirect targets). Prefer this when the user explicitly asks for a regulon. Do not swap to grn_network just because the regulon may be empty or the gene may not be a TF.",
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
            "description": "Predict which TFs best explain a gene set using enrichment over TF regulons. Use this for prompts like 'upstream regulators of these genes', 'which TFs best explain this DEG set', or 'regulate at least 3 of these genes'. Prefer this over grn_shared_regulators when the task is explanatory ranking for a gene set rather than just overlap listing. If the prompt specifies a species such as 'in human', pass that species explicitly.",
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
            "description": "List supported species together with their available capabilities such as expression, motifs, inferred edges, traits, and RNAi support. Use this first for questions like 'which species are available', 'does the atlas have petunia', 'which species support expression data', or capability-coverage comparisons. Prefer this over grn_atlas_overview for exact species/capability checks.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_provenance",
            "description": "Get the exact atlas provenance manifest: version, build metadata, methods, data sources, and DOIs. Use this for prompts about freshness, methods, source papers, or how a layer was generated such as 'what method produced inferred edges' or 'what sources back regulator identification'. Prefer this over grn_atlas_overview for exact provenance details.",
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
            "description": "Compute centrality metrics (degree, betweenness, closeness, eigenvector) for genes. Use this to find top hub genes or transcription factors in a chosen species, especially when the user asks for the top out-degree hub.",
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
            "description": "Design or analyze dsRNA for RNAi gene silencing. Use this first for 'design dsRNA', 'can I silence this gene with RNAi', or 'is this target designable'. If the user also asks what silencing would do, follow with grn_perturbation or grn_network and then grn_enrichment.",
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
            "description": "Screen one or more genes for dsRNA designability and rank them by off-target burden and design cleanliness. Use this when the user asks to compare, rank, or screen candidate genes for RNAi suitability, even if the list contains only one gene.",
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
            "description": "Export regulatory edges with genomic coordinates in JSON or TSV. Use this when the user explicitly asks to export edges or coordinates, even for a single or non-TF gene.",
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
            "description": "Query TF binding motif hits in gene promoters. Given a gene, find what TFs may bind its promoter. Given a TF, find which genes it may regulate via motif evidence. Optionally cross-reference with known regulatory edges. Use this even if the species may be unsupported when the user explicitly asks about promoter motifs, so the tool can return graceful unavailability. Available for arabidopsis, tomato, petunia only.",
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
            "description": "Compare transcription-factor regulatory activity between two tissue or condition groups, based on how each TF's targets shift between group A and group B. Use this for TF-activity-shift questions like 'which TFs change between root and inflorescence' or 'compare petal_limb vs seedling'. Prefer this over grn_differential_expression when the user wants regulators rather than just changed genes. Available for arabidopsis, tomato, petunia.",
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
            "description": "Query expression-inferred regulatory edges from GRNBoost2 or GENIE3. Returns predicted TF-target relationships ranked by importance score. Use this for prompts like 'HY5 inferred regulators', 'GENIE3 predictions for PIL5', or 'expression-based network edges'. If the user also asks what the predicted target set does, represents, or is enriched for, follow this with grn_enrichment on the returned targets. These are computational predictions, not experimentally validated. Available for arabidopsis, tomato, petunia.",
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
            "description": "Report whether a species has the required and optional atlas layers needed for a specific analysis intent, with readiness score and missing layers. Use this for capability-readiness questions like 'can petunia support RNAi analysis' or 'is tomato ready for motif analysis'.",
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
            "name": "grn_phenotype_targeting",
            "description": "Turn a phenotype or design goal into atlas-grounded candidate genes, ranking, readiness, and follow-up recommendations. Use when the user starts from an outcome such as changing flower color or targeting drought-response regulators rather than from a gene list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "species": {"type": "string", "description": "Species name"},
                    "phenotype": {"type": "string", "description": "Phenotype, trait, or design objective"},
                    "intent": {"type": "string", "description": "Research intent such as experiment or rnai"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to keep"},
                    "years_back": {"type": "integer", "description": "Literature recency window"},
                },
                "required": ["species", "phenotype"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_decision_boundary",
            "description": "Produce a single decision-ready summary of what is supported now, unsupported now, ambiguous now, what evidence would overturn the current winner, and the smallest next validation move.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_ids": {"type": "string", "description": "Comma-separated gene IDs or resolvable symbols"},
                    "intent": {"type": "string", "description": "Research intent"},
                    "species": {"type": "string", "description": "Species name"},
                    "max_candidates": {"type": "integer", "description": "Maximum candidates to compare"},
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
            "name": "grn_input_normalization",
            "description": "Normalize messy pasted gene lists, CSV/TSV snippets, aliases, duplicated rows, or mixed-species input before atlas import or analysis. Use this first when the main need is cleanup and deterministic preprocessing rather than immediate biological interpretation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Inline pasted content to normalize"},
                    "filename": {"type": "string", "description": "Optional source filename label"},
                    "species": {"type": "string", "description": "Optional species filter for disambiguation"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grn_dataset_import",
            "description": "Import or map a raw user gene list, DEG list, or simple CSV/TSV content into atlas genes, returning mapped, ambiguous, and unmapped rows. Use this first when the user explicitly provides external content to load, paste, import, or map before analysis. If the user says 'import this hit list, then analyze it', call this first.",
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
            "description": "Run a first-pass atlas workflow over a user-provided gene set: import/mapping summary, enrichment, upstream regulators, candidate triage, and optional subgraph. Use this for prompts like 'analyze this hit list' or 'first-pass analysis of these genes'. Prefer this over grn_research_brief when the user wants analysis results rather than a collaborator-facing brief.",
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

TOOLS.extend(EXTRA_TOOLS)

# ---------------------------------------------------------------------------
# Map tool name -> skill directory name + arg translation
# ---------------------------------------------------------------------------

_TOOL_TO_SKILL = {
    "grn_motif_query": "grn-motif-query",
    "grn_modules": "grn-module",
    "grn_diff_regulation": "grn-diff-regulation",
    "grn_inferred_edges": "grn-infer",
}
_TOOL_TO_SKILL.update(EXTRA_TOOL_TO_SKILL)


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
        "phenotype": "--phenotype",
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
    arg_map.update(EXTRA_ARG_MAP)

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
    raw = trace.get("final_answer") or ""
    ans = raw if isinstance(raw, str) else str(raw)
    return any(ch.isdigit() for ch in ans)


def _evaluate_check_spec(trace, check):
    ct = check["type"]
    if ct == "used_tools_all":
        return all(_used(trace, t) for t in check["tools"])
    if ct == "used_tools_all_any":
        return all(_used(trace, *group) for group in check["tool_groups"])
    if ct == "used_tools_any":
        return _used(trace, *check["tools"])
    if ct == "used_tool_arg_contains":
        return _used_with(trace, check["tool"], check["arg"], check["value"])
    if ct == "n_skills_gte":
        return _n_skills(trace) >= int(check["value"])
    if ct == "answer_has_any":
        return _answer_has_any(trace, *check["terms"])
    if ct == "answer_has_number":
        return _answer_has_number(trace)
    return False


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
            ("used shared-regulator analysis", lambda t: _used(t, "grn_shared_regulators", "grn_network", "grn_subgraph")),
            ("queried both TP53 and MYC", lambda t: (
                _used_with(t, "grn_shared_regulators", "gene_ids", "TP53")
                and _used_with(t, "grn_shared_regulators", "gene_ids", "MYC")
            ) or (
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
            ("called enrichment", lambda t: _used(t, "grn_enrichment", "grn_pathway_enrichment")),
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
            ("called enrichment", lambda t: _used(t, "grn_enrichment", "grn_pathway_enrichment")),
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
            ("used enrichment", lambda t: _used(t, "grn_enrichment", "grn_pathway_enrichment")),
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
            ("called enrichment", lambda t: _used(t, "grn_enrichment", "grn_pathway_enrichment")),
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
            ("called enrichment on overlap", lambda t: _used(t, "grn_enrichment", "grn_pathway_enrichment")),
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
            ("used gene info or gene search on overlap", lambda t: _used(t, "grn_gene_info", "grn_gene_search")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "Export the BibTeX citations for the atlas data sources, then tell me what "
            "data sources and DOIs are recorded in the atlas provenance manifest."
        ),
        "checks": [
            ("used citations", lambda t: _used(t, "grn_citations")),
            ("used provenance", lambda t: _used(t, "grn_provenance")),
            ("mentions doi or source", lambda t: _answer_has_any(t, "doi", "source", "trrust", "jaspar", "plantregmap")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    {
        "question": (
            "Get the full TP53 regulon in human, then run pathway enrichment on the "
            "regulon genes and summarize the main pathways represented."
        ),
        "checks": [
            ("used regulon", lambda t: _used(t, "grn_regulon")),
            ("used enrichment", lambda t: _used(t, "grn_enrichment", "grn_pathway_enrichment")),
            ("mentions pathway or enriched", lambda t: _answer_has_any(t, "pathway", "enrich", "process")),
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
            ("used evidence audit", lambda t: _used(t, "grn_evidence_audit", "grn_multiome_support_audit")),
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
            "Which genes should I target if I want to change flower color in petunia using RNAi? "
            "Start from the phenotype, ground the candidates into the atlas, and tell me the best follow-up mode."
        ),
        "checks": [
            ("used phenotype targeting", lambda t: _used(t, "grn_phenotype_targeting")),
            ("mentions petunia", lambda t: _answer_has(t, "petunia")),
            ("mentions RNAi or dsRNA", lambda t: _answer_has_any(t, "rnai", "dsrna", "follow-up")),
        ],
    },
    {
        "question": (
            "For TP53, BAX, and MDM2 in human, give me one decision-ready summary: "
            "what is supported now, what is still ambiguous, what would overturn the current winner, "
            "and what is the smallest defensible next step?"
        ),
        "checks": [
            ("used decision boundary", lambda t: _used(t, "grn_decision_boundary")),
            ("mentions supported or ambiguous", lambda t: _answer_has_any(t, "supported", "ambiguous", "uncertain")),
            ("mentions next step", lambda t: _answer_has_any(t, "next step", "validation", "defensible")),
        ],
    },
    {
        "question": (
            "Build me a collaborator-ready packet for AN2, JAF13, and DFR in petunia RNAi follow-up, "
            "including uncertainty and strategy comparison."
        ),
        "checks": [
            ("used study packet or report", lambda t: _used(t, "grn_study_packet", "grn_study_report")),
            ("mentions uncertainty or strategy", lambda t: _answer_has_any(t, "uncertainty", "strategy", "comparison")),
            ("mentions petunia", lambda t: _answer_has(t, "petunia")),
        ],
    },
    {
        "question": (
            "I have a messy mixed-species DEG-like paste with TP53, BAX, AT5G11260, and one bad row. "
            "Normalize it first, tell me the likely schema and species mix, then explain what I should do next "
            "before running atlas interpretation."
        ),
        "checks": [
            ("used input normalization", lambda t: _used(t, "grn_input_normalization")),
            ("mentions species or mixed", lambda t: _answer_has_any(t, "species", "mixed", "human", "arabidopsis")),
            ("mentions next step", lambda t: _answer_has_any(t, "next", "import", "filter", "analysis")),
        ],
    },
    {
        "question": (
            "For Arabidopsis HY5, assess whether the conclusion transfers to petunia. "
            "If there is no exact ortholog, tell me the best available family-level analogs and the caveats."
        ),
        "checks": [
            ("used transferability", lambda t: _used(t, "grn_transferability")),
            ("mentions analog or ortholog", lambda t: _answer_has_any(t, "analog", "ortholog", "petunia")),
            ("mentions caveats", lambda t: _answer_has_any(t, "caveat", "unsupported", "uncertain")),
        ],
    },
    {
        "question": (
            "In human, compare pairwise knockout combinations among TP53, MYC, and MDM2. "
            "Tell me whether any combination gives a materially larger predicted impact than the best single-gene intervention."
        ),
        "checks": [
            ("used combinatorial perturbation", lambda t: _used(t, "grn_combinatorial_perturbation")),
            ("used perturbation or consensus", lambda t: _used(t, "grn_perturbation", "grn_consensus_ranking")),
            ("mentions combination or single-gene baseline", lambda t: _answer_has_any(t, "combination", "single-gene", "baseline", "pairwise")),
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
    # =================================================================
    # Category 22: Phenotype-first / literature-guided petunia ideation
    # =================================================================
    {
        "question": (
            "Which genes are the best targets for changing flower color in petunia? "
            "Start with broad literature-guided suggestions, map them into atlas-supported "
            "petunia candidates, and rank the best intervention targets."
        ),
        "checks": [
            ("used literature review or phenotype targeting", lambda t: _used(t, "grn_literature_review", "grn_phenotype_targeting")),
            ("used candidate triage or consensus ranking", lambda t:
                _used(t, "grn_candidate_triage", "grn_consensus_ranking", "grn_phenotype_targeting")),
            ("mentions petunia candidate genes", lambda t:
                _answer_has_any(t, "AN2", "JAF13", "DFR", "petunia")),
            ("mentions ranking or target prioritization", lambda t:
                _answer_has_any(t, "rank", "best target", "candidate", "priority")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    # =================================================================
    # Category 23: Weak-signal / uncertainty handling
    # =================================================================
    {
        "question": (
            "I compared these petunia candidates for flower color change — AN2, JAF13, and DFR — and none looks strongly separated. "
            "What does the current atlas evidence support, what does it not support, and what is the smallest "
            "next experiment that would reduce uncertainty?"
        ),
        "checks": [
            ("used decision boundary or confidence boundary", lambda t: _used(t, "grn_decision_boundary", "grn_confidence_boundary")),
            ("used minimal validation or validation plan or decision boundary", lambda t:
                _used(t, "grn_minimal_validation", "grn_validation_plan", "grn_decision_boundary")),
            ("mentions uncertainty or not supported", lambda t:
                _answer_has_any(t, "uncertain", "does not support", "not support", "confidence", "boundary")),
            ("mentions next experiment or next step", lambda t:
                _answer_has_any(t, "next experiment", "next step", "validation")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    # =================================================================
    # Category 24: Messy import and first-pass recovery
    # =================================================================
    {
        "question": (
            "I pasted a messy DEG list from Excel. Please import it, map what you can, tell me what failed to map, "
            "and then run a first-pass atlas interpretation.\n\n"
            "Gene,log2FC,padj\n"
            "TP53,2.1,0.001\n"
            "BAX,1.8,0.004\n"
            "BADROW,,\n"
            "CDKN1A,1.3,0.01\n"
            "P53,-0.4,0.7"
        ),
        "checks": [
            ("used dataset import", lambda t: _used(t, "grn_dataset_import")),
            ("used user gene-set analysis", lambda t: _used(t, "grn_user_gene_set_analysis")),
            ("mentions unmapped or failed rows", lambda t:
                _answer_has_any(t, "failed", "unmapped", "could not map", "BADROW")),
            ("mentions first-pass interpretation", lambda t:
                _answer_has_any(t, "first-pass", "top ranked", "upstream regulator", "candidate")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    # =================================================================
    # Category 25: Experimental tradeoff comparison
    # =================================================================
    {
        "question": (
            "For petunia flower-color control, compare dsRNA knockdown of JAF13 versus promoter editing of AN2. "
            "Which looks like the more practical first experiment under a modest budget?"
        ),
        "checks": [
            ("used dsrna or dsrna screen", lambda t: _used(t, "grn_dsrna", "grn_dsrna_screen")),
            ("used promoter edit prioritization or crispr", lambda t:
                _used(t, "grn_promoter_edit_prioritization", "grn_crispr_design", "grn_edit_consequence")),
            ("used experiment prioritization or optimizer", lambda t:
                _used(t, "grn_experiment_prioritization", "grn_experiment_optimizer", "grn_intervention_strategy_ranker", "grn_crispr_vs_dsrna_compare")),
            ("mentions comparison language", lambda t:
                _answer_has_any(t, "compare", "more practical", "first experiment", "budget")),
            ("used >= 3 skills", lambda t: _n_skills(t) >= 3),
        ],
    },
    # =================================================================
    # Category 26: Non-model species readiness + ranking
    # =================================================================
    {
        "question": (
            "For petunia, identify candidate regulators of petal pigmentation, then assess whether RNAi "
            "follow-up is actually supported for those candidates."
        ),
        "checks": [
            ("used candidate triage or literature review", lambda t:
                _used(t, "grn_candidate_triage", "grn_literature_review", "grn_user_gene_set_analysis", "grn_phenotype_targeting")),
            ("used coverage report", lambda t: _used(t, "grn_coverage_report")),
            ("mentions RNAi support or coverage", lambda t:
                _answer_has_any(t, "RNAi", "coverage", "supported", "petunia")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
        ],
    },
    # =================================================================
    # Category 27: Literature-grounded mapping into atlas
    # =================================================================
    {
        "question": (
            "Use recent literature to identify the gene families most often implicated in flower-color control "
            "in petunia and related ornamentals, then map those ideas into atlas-supported petunia candidates."
        ),
        "checks": [
            ("used literature review", lambda t: _used(t, "grn_literature_review")),
            ("mentions mapped petunia candidates", lambda t:
                _answer_has_any(t, "AN2", "JAF13", "DFR", "CHS", "petunia")),
            ("mentions family or homolog logic", lambda t:
                _answer_has_any(t, "family", "homolog", "MYB", "bHLH", "WD40")),
            ("used >= 1 skills", lambda t: _n_skills(t) >= 1),
        ],
    },
    # =================================================================
    # Category 28: Honest species/coverage boundary explanation
    # =================================================================
    {
        "question": (
            "Tell me honestly what the atlas can and cannot support today for petunia flower-color intervention planning."
        ),
        "checks": [
            ("used coverage report or species", lambda t: _used(t, "grn_coverage_report", "grn_species")),
            ("mentions can and cannot support", lambda t:
                _answer_has_any(t, "can support", "cannot support", "not supported", "petunia")),
            ("mentions intervention planning or RNAi or expression", lambda t:
                _answer_has_any(t, "intervention", "RNAi", "expression", "network", "validation")),
            ("used >= 1 skills", lambda t: _n_skills(t) >= 1),
        ],
    },
    # =================================================================
    # Category 29: Strategy comparison: single vs combo perturbation
    # =================================================================
    {
        "question": (
            "For TP53, compare single-gene knockout versus double knockout with MYC. "
            "Which strategy is more likely to reveal broader downstream network effects?"
        ),
        "checks": [
            ("used perturbation or combinatorial perturbation", lambda t:
                _used(t, "grn_perturbation", "grn_combinatorial_perturbation")),
            ("mentions single vs double comparison", lambda t:
                _answer_has_any(t, "single", "double", "broader", "downstream effect")),
            ("mentions which is more likely", lambda t:
                _answer_has_any(t, "more likely", "broader", "larger", "stronger")),
            ("used >= 1 skills", lambda t: _n_skills(t) >= 1),
        ],
    },
    # =================================================================
    # Category 30: Unsupported-analysis boundary quality
    # =================================================================
    {
        "question": (
            "Do full cell-type regulatory analysis for TP53 and BAX right now."
        ),
        "checks": [
            ("used celltype readiness", lambda t: _used(t, "grn_celltype_regulation")),
            ("mentions missing layers or readiness", lambda t:
                _answer_has_any(t, "missing", "not supported", "readiness", "cell-type", "single-cell")),
            ("used >= 1 skills", lambda t: _n_skills(t) >= 1),
        ],
    },
    # =================================================================
    # Category 31: Mixed-species import boundary
    # =================================================================
    {
        "question": (
            "Import this mixed-species list and tell me what can be analyzed cleanly in human versus Arabidopsis: "
            "TP53, AT5G11260, BAX, HY5."
        ),
        "checks": [
            ("used dataset import or gene search", lambda t: _used(t, "grn_dataset_import", "grn_gene_search")),
            ("mentions both human and Arabidopsis", lambda t:
                _answer_has_any(t, "human", "arabidopsis", "AT5G11260", "TP53")),
            ("mentions cleanly analyzed or species separation", lambda t:
                _answer_has_any(t, "cleanly", "species", "separate", "mixed-species", "can be analyzed")),
            ("used >= 1 skills", lambda t: _n_skills(t) >= 1),
        ],
    },
]

_SUPP_PATHS = sorted(SKILLS_DIR.glob("_test_llm_orchestration_*.json"))
for _supp_path in _SUPP_PATHS:
    for q in json.loads(_supp_path.read_text()):
        checks = []
        for spec in q.get("checks_spec", []):
            desc = spec.get("label") or spec["type"]
            checks.append((desc, lambda t, spec=spec: _evaluate_check_spec(t, spec)))
        QUESTIONS.append({"question": q["question"], "checks": checks, "label": q.get("label"), "covers_tools": q.get("covers_tools", [])})


# ---------------------------------------------------------------------------
# Provider-backed chat completion
# ---------------------------------------------------------------------------

def resolve_provider(model: str, provider: str = "auto") -> str:
    if provider and provider != "auto":
        return provider
    return "openai" if model.startswith("gpt-") else "openrouter"


def get_api_key(provider: str) -> str | None:
    env_name = "OPENAI_API_KEY" if provider == "openai" else "OPENROUTER_API_KEY"
    return os.environ.get(env_name)


def chat_completion(messages: list, model: str, api_key: str, provider: str = "auto") -> dict:
    provider = resolve_provider(model, provider)
    api_url = OPENAI_URL if provider == "openai" else OPENROUTER_URL
    payload_obj = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
    }
    if provider == "openai":
        payload_obj["max_completion_tokens"] = 4096
    else:
        payload_obj["max_tokens"] = 4096
    payload = json.dumps(payload_obj).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_err = None
    for attempt in range(API_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            last_err = {"message": f"HTTP Error {e.code}: {body[:300]}"}
            if (
                e.code == 429
                or "rate limit" in body.lower()
                or "too many requests" in body.lower()
                or "upstream idle timeout exceeded" in body.lower()
                or "timed out" in body.lower()
            ):
                time.sleep(min(API_BACKOFF_S * (2 ** attempt), 60))
                continue
            raise
        except Exception as e:
            msg = str(e)
            last_err = {"message": msg}
            if (
                "429" in msg
                or "rate limit" in msg.lower()
                or "too many requests" in msg.lower()
                or "upstream idle timeout exceeded" in msg.lower()
                or "timed out" in msg.lower()
            ):
                time.sleep(min(API_BACKOFF_S * (2 ** attempt), 60))
                continue
            raise
    return {"error": last_err or {"message": "api request failed after retries"}}


SYSTEM_PROMPT = """\
You are a bioinformatics research assistant with access to the GRN Atlas \
gene regulatory network database. You have tools to search genes, explore \
regulatory networks, run enrichment analyses, predict perturbation effects, \
design dsRNA, and more.

When answering questions:
1. Use the available tools to gather data — don't guess.
2. Do not answer from prior knowledge when the question is about genes, regulators, dsRNA, perturbation, enrichment, or atlas content. Make at least one tool call first.
3. If the question asks for multiple things, complete every requested subtask before giving the final answer. Do not stop after the first useful tool.
4. If the prompt explicitly asks you to run, compare, enrich, validate, or summarize a second analysis on the results of a first analysis, you must make the second tool call as well. Do not treat the first tool result as sufficient.
5. Prefer the most direct specialized tool when one exists:
   - cleanup/normalization of messy pasted input before import -> grn_input_normalization
   - shared/common regulators across multiple genes -> grn_shared_regulators
   - best upstream TFs explaining a gene set, DEG set, or min-overlap style upstream analysis -> grn_upstream
   - if the user explicitly says regulon -> grn_regulon, even if the gene may be non-TF or have zero targets
   - regulon active in one imported cell state / cluster -> grn_celltype_regulon, not grn_celltype_upstream
   - promoter motif questions, even for unsupported species -> grn_motif_query
   - promoter/chromatin/enhancer support audit for one explicit TF→target edge -> grn_cis_support_audit
   - broader multi-layer evidence audit for one explicit TF→target edge across network, motif, chromatin, expression, and perturbation -> grn_multiome_support_audit
   - dsRNA or RNAi designability for one gene -> grn_dsrna
   - direct dsRNA-versus-CRISPR modality comparison for the same gene set -> grn_crispr_vs_dsrna_compare
   - predict consequences of a promoter edit, motif disruption, or coding edit -> grn_edit_consequence
   - enhancer-linked neighborhood around one gene -> grn_enhancer_network
   - rank intervention modalities across candidate genes under an explicit budget or intent -> grn_intervention_strategy_ranker
   - map literature gene symbols, ortholog labels, or family cues into atlas-grounded candidates -> grn_literature_grounding
   - start from a peak or genomic region and ask which genes it likely regulates -> grn_peak_gene_linkage
   - identify drivers of a transition from branch labels or a transition gene signature -> grn_transition_drivers
   - what silencing / knockout changes -> grn_perturbation
   - what GO terms or pathways are enriched -> grn_enrichment
6. Common RNAi chain: if asked whether a dsRNA can be designed and what silencing would do, call grn_dsrna, then grn_perturbation or grn_network, then grn_enrichment.
7. Common discovery chain: if asked which species support a capability, call grn_species first, choose one matching species from the result, then continue the remaining requested analysis steps in that species.
8. Common import-first chain: if the user explicitly says import or map a hit list before analysis, call grn_dataset_import first, then call grn_user_gene_set_analysis or the requested downstream analysis.
9. Common imported-omics chain: if the user asks to import an expression matrix or fixture and then do cell-state, trajectory, pseudotime, or packaged workflow analysis, call grn_omics_import first and wait for a successful dataset_id. Then use that returned dataset_id for grn_celltype_compare, grn_celltype_upstream, grn_trajectory_drivers, grn_pseudotime_activity, or grn_workflow as requested. Do not stop after import if the user asked for downstream imported-dataset analysis.
10. Common inferred-validation chain: if the user asks for inferred edges or inferred regulators and then asks whether they also appear in the curated network, call grn_inferred_edges first, then call grn_network for the curated validation step.
11. Common phenotype-first chain: if the user starts from a phenotype or design intent rather than a gene list, especially in a non-model species such as petunia, prefer grn_phenotype_targeting. Use grn_literature_review only when the user explicitly wants paper-level context or recent external literature.
12. Common support-readiness chain: if the user asks whether a candidate, species, or proposed follow-up is actually supported for RNAi, expression, conservation, or another atlas workflow, call grn_coverage_report after the candidate-discovery step instead of answering from general impressions.
13. Common uncertainty-boundary chain: if the user explicitly says confidence boundary, call grn_confidence_boundary. Otherwise, if the user asks what the atlas supports, does not support, what remains uncertain, or what smallest next step reduces uncertainty, prefer grn_decision_boundary. If the wording is weak-signal or generic but still asks about current atlas evidence, support vs non-support, uncertainty, or the smallest next experiment, you still must call grn_decision_boundary or grn_confidence_boundary rather than answer from general reasoning alone. If needed, expand it with grn_confidence_boundary and grn_minimal_validation.
14. Common inferred-compare chain: if the user asks to compare GRNBoost2 and GENIE3 and then inspect the overlapping TFs, call grn_inferred_edges for both methods first, then call grn_gene_info or grn_gene_search on at least one overlapping TF before finishing.
15. Common inferred-enrichment chain: if the user asks for GRNBoost2 or GENIE3 predicted targets and then asks what processes those targets represent, call grn_inferred_edges first and then call grn_enrichment on the returned target set before answering.
16. If the user explicitly asks for inferred targets, inferred regulators, GRNBoost2, or GENIE3, you must still call grn_inferred_edges even if you suspect the requested species may not have inferred-edge coverage. Let the tool report unavailability rather than skipping it.
17. If the user explicitly asks for pathway enrichment, prefer grn_pathway_enrichment over grn_enrichment unless the request also explicitly asks for GO terms, motifs, or mixed enrichment types.
18. If the user asks you to design a CRISPR guide and then evaluate off-target risk, you must call grn_crispr_design first and then call grn_crispr_offtargets on one concrete designed guide before finishing.
19. If the user asks for literature names from other species to be grounded into atlas-supported candidates and then prioritized for intervention, call grn_literature_grounding before candidate ranking or dsRNA/CRISPR follow-up.
20. If the user asks for a region-to-gene interpretation and then a follow-up neighborhood or support audit, call grn_peak_gene_linkage first and use a returned or discussed gene for the second step.
21. If the user asks for state-transition drivers and then asks what that top driver regulates in one state, call grn_transition_drivers first and then grn_celltype_regulon or grn_regulon for the selected driver.
22. If the user asks for cell-type, single-cell, or cluster-specific regulatory analysis but has not supplied an imported dataset, do not only ask for missing inputs in plain text. First call grn_celltype_regulation so the atlas can report readiness and missing layers.
23. In the final answer, explicitly state the requested conclusion words when relevant (for example conserved/not conserved, ortholog, mouse, shared regulators, enriched pathways) instead of implying them.
24. Synthesize the tool results into a clear, data-backed answer.
25. Cite specific numbers from the tool outputs.

Key gene IDs to know:
- Human genes use symbols directly: TP53, MYC, BAX, NFKB1, E2F1, etc.
- Arabidopsis genes use AGI locus IDs: AT5G11260 (HY5), AT1G49720 (ABF1), AT2G43010 (PIF4)
- Tomato genes use Solyc IDs.
"""


def run_question(question: str, model: str, api_key: str, http_url: str | None,
                 provider: str = "auto",
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
            response = chat_completion(messages, model, api_key, provider=provider)
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
    parser.add_argument("--provider", default="auto", choices=["auto", "openrouter", "openai"])
    parser.add_argument("--http", default=os.environ.get("LLM_TEST_HTTP"), help="GRN Atlas server URL")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--question", type=int, default=None, help="Run only question N (1-indexed)")
    args = parser.parse_args()

    provider = resolve_provider(args.model, args.provider)
    api_key = get_api_key(provider)
    if not api_key:
        env_name = "OPENAI_API_KEY" if provider == "openai" else "OPENROUTER_API_KEY"
        print(f"ERROR: Set {env_name} environment variable", file=sys.stderr)
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
        trace = run_question(q["question"], args.model, api_key, args.http, provider, args.verbose)
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
            "tool_calls": trace["tool_calls"],
            "final_answer": trace.get("final_answer"),
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
