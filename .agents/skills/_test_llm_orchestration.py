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
    }

    _BOOL_FLAGS = {"include_edge_support", "compare_curated"}

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
    ans = (trace.get("final_answer") or "").lower()
    return all(t.lower() in ans for t in terms)

def _answer_has_any(trace, *terms):
    """Check if the final answer contains any of the terms."""
    ans = (trace.get("final_answer") or "").lower()
    return any(t.lower() in ans for t in terms)

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
            "I want to design an RNAi screen targeting the Arabidopsis orthologs of the "
            "light-response genes HY5 (AT5G11260) and PIF4 (AT2G43010). "
            "Screen both for dsRNA designability, and for whichever has better specificity, "
            "predict the downstream perturbation effects of silencing it."
        ),
        "checks": [
            ("used dsrna_screen or dsrna", lambda t: _used(t, "grn_dsrna_screen", "grn_dsrna")),
            ("used perturbation", lambda t: _used(t, "grn_perturbation")),
            ("mentions specificity or off-target", lambda t:
                _answer_has_any(t, "specific", "off-target", "off_target")),
            ("used >= 2 skills", lambda t: _n_skills(t) >= 2),
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
                sum(1 for c in t["tool_calls"]
                    if c["name"] == "grn_inferred_edges") >= 2
                or _answer_has_any(t, ["GRNBoost2", "GENIE3", "both"])),
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
