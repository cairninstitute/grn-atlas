#!/usr/bin/env python3
"""
HTTP-mode test suite for GRN Atlas AgentSkills.
Mirrors the direct-mode tests but passes --http http://localhost:8000.
"""
import json
import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
PYTHON = str(REPO_ROOT / "backend" / "venv" / "bin" / "python")
HTTP = "http://localhost:8000"

results = []


def run_skill(skill_name: str, args: list[str], label: str, raw: bool = False) -> dict:
    script = SKILLS_DIR / skill_name / "scripts" / "run.py"
    cmd = [PYTHON, str(script), "--http", HTTP] + args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(REPO_ROOT))
        if proc.returncode != 0:
            return {"skill": skill_name, "label": label, "status": "ERROR",
                    "error": proc.stderr.strip()[-500:], "data": None}
        if raw:
            return {"skill": skill_name, "label": label, "status": "OK",
                    "data": proc.stdout, "error": None}
        data = json.loads(proc.stdout)
        return {"skill": skill_name, "label": label, "status": "OK", "data": data, "error": None}
    except subprocess.TimeoutExpired:
        return {"skill": skill_name, "label": label, "status": "TIMEOUT", "data": None, "error": "timeout"}
    except json.JSONDecodeError as e:
        return {"skill": skill_name, "label": label, "status": "JSON_ERROR",
                "data": None, "error": f"Bad JSON: {e}; stdout={proc.stdout[:300]}"}
    except Exception as e:
        return {"skill": skill_name, "label": label, "status": "EXCEPTION",
                "data": None, "error": str(e)}


def grade(result: dict, checks: list[tuple[str, callable]]) -> dict:
    if result["status"] != "OK":
        result["grade"] = "FAIL"
        result["checks"] = [{"check": "execution", "pass": False, "detail": result["error"]}]
        return result
    check_results = []
    all_pass = True
    for desc, pred in checks:
        try:
            passed = pred(result["data"])
        except Exception as e:
            passed = False
            desc += f" [exception: {e}]"
        check_results.append({"check": desc, "pass": passed})
        if not passed:
            all_pass = False
    result["grade"] = "PASS" if all_pass else "FAIL"
    result["checks"] = check_results
    return result


def G(d):
    if isinstance(d, list):
        return d
    return d.get("results", d.get("genes", []))


# =====================================================================
# 1. grn-gene-search
# =====================================================================

r = run_skill("grn-gene-search", ["--query", "TP53", "--species", "human", "--limit", "5"],
              "search: TP53 in human")
grade(r, [
    ("first result is TP53", lambda d: G(d)[0]["symbol"] == "TP53"),
    ("species is human", lambda d: G(d)[0]["species"] == "human"),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "MYB", "--species", "arabidopsis", "--limit", "3"],
              "search: MYB arabidopsis")
grade(r, [
    ("all arabidopsis", lambda d: all(g["species"] == "arabidopsis" for g in G(d))),
    ("<=3 results", lambda d: len(G(d)) <= 3),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "ZZZZNOTAREAL_GENE_XYZ", "--species", "human"],
              "search: nonexistent gene")
grade(r, [("empty results", lambda d: len(G(d)) == 0)])
results.append(r)

# =====================================================================
# 2. grn-gene-info
# =====================================================================

r = run_skill("grn-gene-info", ["--gene-id", "TP53"], "info: TP53")
grade(r, [
    ("id=TP53", lambda d: d.get("id") == "TP53"),
    ("human", lambda d: d.get("species") == "human"),
    ("is_tf", lambda d: d.get("is_tf") is True),
])
results.append(r)

r = run_skill("grn-gene-info", ["--gene-id", "FAKEGENE999"], "info: nonexistent")
grade(r, [
    ("error response", lambda d: "error" in d or d.get("id") is None),
])
results.append(r)

# =====================================================================
# 3. grn-network
# =====================================================================

r = run_skill("grn-network", ["--gene-id", "TP53"], "network: TP53 both")
grade(r, [
    ("has regulators", lambda d: len(d.get("regulators", [])) > 0),
    ("has targets", lambda d: len(d.get("targets", [])) > 0),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "TP53", "--direction", "targets"],
              "network: TP53 targets only")
grade(r, [
    ("has targets", lambda d: len(d.get("targets", [])) > 0),
    ("no regulators", lambda d: len(d.get("regulators", [])) == 0),
])
results.append(r)

# =====================================================================
# 4. grn-pathfinding
# =====================================================================

r = run_skill("grn-pathfinding", ["--source", "TP53", "--target", "BAX", "--max-depth", "1"],
              "pathfinding: TP53->BAX direct")
grade(r, [
    ("has paths", lambda d: len(d.get("paths", [])) > 0),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "TP53", "--target", "ZZZZFAKE"],
              "pathfinding: nonexistent target")
grade(r, [
    ("handles gracefully", lambda d: isinstance(d, dict)),
])
results.append(r)

# =====================================================================
# 5. grn-enrichment (incl. single-gene trait)
# =====================================================================

r = run_skill("grn-enrichment", ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--type", "go"],
              "enrichment: GO 5 genes")
grade(r, [
    ("non-empty", lambda d: len(d.get("enriched_terms", d.get("results", d if isinstance(d, list) else []))) > 0),
])
results.append(r)

r = run_skill("grn-enrichment", ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--type", "pathway"],
              "enrichment: pathway")
grade(r, [
    ("non-empty", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-enrichment", ["--gene-id", "TP53", "--type", "trait"],
              "enrichment: single-gene trait TP53")
grade(r, [
    ("has gene_id", lambda d: d.get("gene_id") == "TP53"),
    ("has traits", lambda d: len(d.get("traits", [])) > 0),
    ("has cancer trait", lambda d: any("cancer" in t["trait"].lower() for t in d["traits"])),
])
results.append(r)

r = run_skill("grn-enrichment", ["--gene-id", "FAKEGENE", "--type", "trait"],
              "enrichment: single-gene trait nonexistent")
grade(r, [
    ("empty traits", lambda d: len(d.get("traits", [])) == 0),
])
results.append(r)

# =====================================================================
# 6. grn-expression
# =====================================================================

r = run_skill("grn-expression", ["--gene-id", "AT1G49720"], "expression: ABF1")
grade(r, [("has data", lambda d: isinstance(d, (list, dict)) and len(d) > 0)])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "TP53"], "expression: human (no data)")
grade(r, [("handles gracefully", lambda d: isinstance(d, (list, dict)))])
results.append(r)

# =====================================================================
# 7. grn-coexpression
# =====================================================================

r = run_skill("grn-coexpression", ["--gene-id", "AT1G49720", "--top", "5"],
              "coexpr: ABF1 top 5")
grade(r, [("has results", lambda d: isinstance(d, (list, dict)) and len(d) > 0)])
results.append(r)

# =====================================================================
# 8. grn-perturbation
# =====================================================================

r = run_skill("grn-perturbation", ["--gene-id", "TP53", "--action", "ko"],
              "perturb: TP53 ko")
grade(r, [("has effects", lambda d: isinstance(d, dict) and len(d) > 0)])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-ids", "TP53:ko,MYC:oe"],
              "perturb: multi-intervention")
grade(r, [("has effects", lambda d: isinstance(d, dict) and len(d) > 0)])
results.append(r)

# =====================================================================
# 9. grn-dsrna
# =====================================================================

r = run_skill("grn-dsrna", ["--target-gene", "AT1G49720", "--species", "arabidopsis"],
              "dsrna: design ABF1")
grade(r, [
    ("mode=design", lambda d: d.get("mode") == "design"),
    ("has design", lambda d: "design" in d),
])
results.append(r)

r = run_skill("grn-dsrna", ["--sequence", "ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCA",
                             "--species", "arabidopsis"],
              "dsrna: analyze sequence")
grade(r, [
    ("mode=analyze", lambda d: d.get("mode") == "analyze"),
])
results.append(r)

r = run_skill("grn-dsrna", ["--target-gene", "TP53", "--species", "human"],
              "dsrna: human (no transcripts)")
grade(r, [
    ("available=false", lambda d: d.get("available") is False),
])
results.append(r)

# =====================================================================
# 10. grn-orthology
# =====================================================================

r = run_skill("grn-orthology", ["--gene-id", "TP53"], "ortho: TP53 default")
grade(r, [
    ("has human", lambda d: "human" in d),
    ("human found", lambda d: d["human"]["found"] is True),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "TP53", "--species", "mouse"],
              "ortho: TP53->mouse")
grade(r, [("has mouse", lambda d: "mouse" in d)])
results.append(r)

# =====================================================================
# 11. grn-conservation
# =====================================================================

r = run_skill("grn-conservation",
              ["--gene-ids", "TP53,BAX,BCL2", "--species-b", "mouse"],
              "conserv: 3 genes -> mouse")
grade(r, [("returns data", lambda d: isinstance(d, (list, dict)) and len(d) > 0)])
results.append(r)

# =====================================================================
# 12. grn-subgraph
# =====================================================================

r = run_skill("grn-subgraph", ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2"],
              "subgraph: 5 genes")
grade(r, [
    ("has edges", lambda d: len(d.get("edges", d.get("interactions", []))) > 0),
])
results.append(r)

# =====================================================================
# 13. grn-export
# =====================================================================

r = run_skill("grn-export", ["--gene-ids", "TP53,BAX", "--format", "json"],
              "export: JSON")
grade(r, [
    ("has edges", lambda d: "edges" in d),
    ("TP53->BAX present", lambda d: any(
        e["source_gene_id"] == "TP53" and e["target_gene_id"] == "BAX" for e in d["edges"])),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "TP53,BAX", "--format", "tsv"],
              "export: TSV", raw=True)
grade(r, [
    ("starts with comment", lambda d: d.startswith("# GRN Atlas")),
    ("has TP53", lambda d: "TP53" in d),
    ("tab-separated", lambda d: "\t" in d),
])
results.append(r)

# =====================================================================
# 14. grn-provenance (incl. freshness)
# =====================================================================

r = run_skill("grn-provenance", [], "prov: manifest")
grade(r, [
    ("has atlas_version", lambda d: "atlas_version" in d),
    ("has sources", lambda d: len(d.get("sources", [])) > 0),
])
results.append(r)

r = run_skill("grn-provenance", ["--freshness"], "prov: freshness")
grade(r, [
    ("has sources", lambda d: isinstance(d.get("sources"), list) and len(d["sources"]) > 0),
    ("has checked", lambda d: "checked" in d),
    ("has stale list", lambda d: isinstance(d.get("stale"), list)),
])
results.append(r)

# =====================================================================
# 15. grn-species
# =====================================================================

r = run_skill("grn-species", [], "species: all")
grade(r, [
    ("has species", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
    ("human present", lambda d: "human" in str(d)),
])
results.append(r)

# =====================================================================
# 16. grn-stats
# =====================================================================

r = run_skill("grn-stats", [], "stats: global")
grade(r, [
    ("has genes", lambda d: d.get("genes", 0) > 1000),
    ("has species count", lambda d: d.get("species", 0) >= 5),
    ("has interactions", lambda d: d.get("interactions", 0) > 1000),
])
results.append(r)

r = run_skill("grn-stats", ["--species", "human"], "stats: human")
grade(r, [
    ("species=human", lambda d: d.get("species") == "human"),
    ("has genes", lambda d: d.get("genes", 0) > 0),
    ("has TFs", lambda d: d.get("transcription_factors", 0) > 0),
])
results.append(r)

r = run_skill("grn-stats", ["--species", "FAKEFAKE"], "stats: nonexistent")
grade(r, [("handles gracefully", lambda d: isinstance(d, dict))])
results.append(r)

# =====================================================================
# 17. grn-cascade
# =====================================================================

r = run_skill("grn-cascade", ["--target-gene", "TP53", "--interventions", "SIRT1:up:1.5"],
              "cascade: TP53 SIRT1 up")
grade(r, [
    ("has cascade", lambda d: isinstance(d.get("cascade"), list) and len(d["cascade"]) > 0),
    ("has affected_genes", lambda d: d.get("affected_genes", 0) > 0),
    ("effects have fields", lambda d: all(
        "id" in e and "direction" in e and "magnitude" in e for e in d["cascade"])),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "TP53", "--interventions", "SIRT1:up:1.5,MDM2:down:0.5"],
              "cascade: two interventions")
grade(r, [
    ("has cascade", lambda d: len(d.get("cascade", [])) > 0),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "FAKEGENE", "--interventions", "X:up:1.0"],
              "cascade: nonexistent gene")
grade(r, [("handles gracefully", lambda d: isinstance(d, dict))])
results.append(r)

# =====================================================================
# 18. grn-citations
# =====================================================================

r = run_skill("grn-citations", [], "citations: BibTeX", raw=True)
grade(r, [
    ("non-empty", lambda d: len(d.strip()) > 0),
    ("has @article", lambda d: "@article" in d or "@misc" in d),
    ("has TRRUST", lambda d: "trrust" in d.lower() or "TRRUST" in d),
    ("has DOI", lambda d: "doi" in d.lower()),
    ("multiple entries", lambda d: d.count("@") >= 2),
])
results.append(r)

# =====================================================================
# 19. grn-dsrna-screen
# =====================================================================

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720,AT5G11260,AT2G43010", "--species", "arabidopsis"],
              "screen: 3 arabidopsis genes")
grade(r, [
    ("available=true", lambda d: d.get("available") is True),
    ("n_genes=3", lambda d: d.get("n_genes") == 3),
    ("has results", lambda d: len(d.get("results", [])) == 3),
    ("has designable", lambda d: isinstance(d.get("designable"), int)),
    ("results have fields", lambda d: all(
        "gene_id" in r and "designable" in r and "symbol" in r for r in d["results"])),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "TP53,MYC", "--species", "human"],
              "screen: human (no transcripts)")
grade(r, [
    ("available=false", lambda d: d.get("available") is False),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720,AT5G11260", "--species", "arabidopsis",
               "--no-predict-effect"],
              "screen: no effect prediction")
grade(r, [
    ("available=true", lambda d: d.get("available") is True),
    ("no effect", lambda d: d.get("predicted_effect") is None),
])
results.append(r)


# =====================================================================
# GRN-REGULON (HTTP)
# =====================================================================
r = run_skill("grn-regulon", ["--gene-id", "TP53", "--depth", "1"],
              "regulon: TP53 depth=1")
grade(r, [
    ("found", lambda d: d.get("found") is True),
    ("total >= 100", lambda d: d.get("total", 0) >= 100),
])
results.append(r)

r = run_skill("grn-regulon", ["--gene-id", "NONEXISTENT_XYZ"],
              "regulon: nonexistent gene error")
grade(r, [
    ("error returned", lambda d: "error" in d),
])
results.append(r)

# =====================================================================
# GRN-REGULON-COMPARE (HTTP)
# =====================================================================
r = run_skill("grn-regulon-compare", ["--tf-a", "TP53", "--tf-b", "MYC", "--depth", "1"],
              "regulon-compare: TP53 vs MYC")
grade(r, [
    ("has jaccard", lambda d: 0 <= d.get("jaccard", -1) <= 1),
    ("overlap > 0", lambda d: d.get("overlap_size", 0) > 0),
])
results.append(r)

# =====================================================================
# GRN-UPSTREAM (HTTP)
# =====================================================================
r = run_skill("grn-upstream",
              ["--gene-ids", "BAX,BCL2,CDKN1A,MDM2,GADD45A"],
              "upstream: TP53 targets predict TP53")
grade(r, [
    ("has regulators", lambda d: len(d.get("regulators", [])) > 0),
    ("TP53 in top 5", lambda d: "TP53" in [x.get("symbol") for x in d.get("regulators", [])[:5]]),
])
results.append(r)

# =====================================================================
# GRN-NETWORK-PATTERNS (HTTP)
# =====================================================================
r = run_skill("grn-network-patterns",
              ["--species", "human", "--types", "autoregulation"],
              "patterns: human autoregulation")
grade(r, [
    ("has patterns", lambda d: len(d.get("patterns", [])) > 0),
    ("BCL6 present", lambda d: any("BCL6" in str(p) for p in d.get("patterns", []))),
])
results.append(r)

# =====================================================================
# GRN-CENTRALITY (HTTP)
# =====================================================================
r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "out_degree", "--top", "5"],
              "centrality: human out-degree top 5")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("at most 5", lambda d: len(d.get("results", [])) <= 5),
])
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "betweenness", "--top", "5"],
              "centrality: betweenness HTTP")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("metric is betweenness", lambda d: d.get("metric") == "betweenness"),
])
results.append(r)

# =====================================================================
# GRN-MOTIF (HTTP)
# =====================================================================
r = run_skill("grn-motif",
              ["--gene-id", "AT5G11260", "--species", "arabidopsis", "--top", "5"],
              "motif: HY5 promoter hits HTTP")
grade(r, [
    ("has hits key", lambda d: "hits" in d),
])
results.append(r)

r = run_skill("grn-motif",
              ["--tf-gene-id", "AT5G11260", "--species", "arabidopsis", "--top", "5"],
              "motif: HY5 as TF HTTP")
grade(r, [
    ("has hits key", lambda d: "hits" in d),
])
results.append(r)

r = run_skill("grn-motif",
              ["--gene-id", "TP53", "--species", "human"],
              "motif: human graceful degradation HTTP")
grade(r, [
    ("empty hits", lambda d: len(d.get("hits", [])) == 0),
])
results.append(r)

# =====================================================================
# GRN-MODULE (HTTP)
# =====================================================================
r = run_skill("grn-module",
              ["--species", "arabidopsis", "--top-modules", "5"],
              "module: arabidopsis louvain HTTP")
grade(r, [
    ("has modules", lambda d: len(d.get("modules", [])) > 0),
    ("at most 5", lambda d: len(d.get("modules", [])) <= 5),
])
results.append(r)

r = run_skill("grn-module",
              ["--species", "human", "--algorithm", "louvain", "--top-modules", "3"],
              "module: human louvain HTTP")
grade(r, [
    ("has modules", lambda d: "modules" in d),
])
results.append(r)

# =====================================================================
# GRN-DIFF-REGULATION (HTTP)
# =====================================================================
r = run_skill("grn-diff-regulation",
              ["--species", "arabidopsis", "--group-a", "root", "--group-b", "inflorescence", "--top", "5"],
              "diff-reg: arabidopsis root vs inflorescence HTTP")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("species correct", lambda d: d.get("species") == "arabidopsis"),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "petunia", "--group-a", "petal", "--group-b", "sepal", "--top", "3"],
              "diff-reg: petunia petal vs sepal HTTP")
grade(r, [
    ("has results key", lambda d: "results" in d),
])
results.append(r)

# =====================================================================
# GRN-INFER (HTTP)
# =====================================================================
r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--top", "5"],
              "infer: arabidopsis top edges HTTP")
grade(r, [
    ("has edges", lambda d: len(d.get("edges", [])) > 0),
    ("at most 5", lambda d: len(d.get("edges", [])) <= 5),
    ("has note", lambda d: "note" in d),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--method", "GRNBoost2", "--top", "3"],
              "infer: GRNBoost2 filter HTTP")
grade(r, [
    ("all GRNBoost2", lambda d: all(e["method"] == "GRNBoost2" for e in d["edges"])),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--gene-id", "AT5G11260", "--compare-curated"],
              "infer: compare curated HTTP")
grade(r, [
    ("has curated field", lambda d: any("has_curated_support" in e for e in d.get("edges", []))),
])
results.append(r)

# =====================================================================
# GRN-EVIDENCE-AUDIT (HTTP)
# =====================================================================
r = run_skill("grn-evidence-audit",
              ["--scope", "gene", "--gene-id", "TP53"],
              "evidence audit: gene TP53 HTTP")
grade(r, [
    ("supported gene", lambda d: d.get("summary", {}).get("supported") is True),
    ("has confidence", lambda d: "confidence" in d),
])
results.append(r)

r = run_skill("grn-evidence-audit",
              ["--scope", "edge", "--source-id", "TP53", "--target-id", "BAX"],
              "evidence audit: edge TP53->BAX HTTP")
grade(r, [
    ("has support counts", lambda d: "support_counts" in d.get("evidence_summary", {})),
])
results.append(r)

# =====================================================================
# GRN-COVERAGE-REPORT (HTTP)
# =====================================================================
r = run_skill("grn-coverage-report",
              ["--species", "arabidopsis", "--intent", "expression"],
              "coverage report: arabidopsis expression HTTP")
grade(r, [
    ("has readiness score", lambda d: "readiness_score" in d),
    ("has recommended skills", lambda d: len(d.get("recommended_skills", [])) > 0),
])
results.append(r)

r = run_skill("grn-coverage-report",
              ["--species", "human", "--intent", "traits"],
              "coverage report: human traits HTTP")
grade(r, [
    ("traits layer available", lambda d: d.get("available_layers", {}).get("trait_associations", 0) > 0),
])
results.append(r)

# =====================================================================
# GRN-CANDIDATE-TRIAGE (HTTP)
# =====================================================================
r = run_skill("grn-candidate-triage",
              ["--gene-ids", "TP53,BAX,MDM2", "--intent", "network"],
              "candidate triage: TP53,BAX,MDM2 HTTP")
grade(r, [
    ("has ranked candidates", lambda d: len(d.get("ranked_candidates", [])) > 0),
    ("TP53 ranks first", lambda d: d.get("ranked_candidates", [{}])[0].get("gene_id") == "TP53"),
])
results.append(r)

r = run_skill("grn-candidate-triage",
              ["--gene-ids", "TP53,NOPE", "--intent", "experiment"],
              "candidate triage: missing gene handling HTTP")
grade(r, [
    ("tracks excluded genes", lambda d: any(g.get("gene_id") == "NOPE" for g in d.get("excluded_genes", []))),
])
results.append(r)

# =====================================================================
# GRN-EXPERIMENT-PRIORITIZATION (HTTP)
# =====================================================================
r = run_skill("grn-experiment-prioritization",
              ["--gene-ids", "TP53", "--intent", "experiment"],
              "experiment prioritization: TP53 HTTP")
grade(r, [
    ("has plan", lambda d: len(d.get("plans", [])) > 0),
    ("has recommended experiments", lambda d: len(d.get("plans", [{}])[0].get("recommended_experiments", [])) > 0),
])
results.append(r)

r = run_skill("grn-experiment-prioritization",
              ["--gene-ids", "Peaxi162Scf00118g00310", "--intent", "rnai", "--species", "petunia"],
              "experiment prioritization: petunia rnai HTTP")
grade(r, [
    ("includes dsrna option", lambda d: any(e.get("experiment") == "dsrna_design"
                                             for e in d.get("plans", [{}])[0].get("recommended_experiments", []))),
])
results.append(r)

# =====================================================================
# GRN-CONFIDENCE-BOUNDARY (HTTP)
# =====================================================================
r = run_skill("grn-confidence-boundary",
              ["--gene-ids", "TP53,BAX", "--intent", "experiment"],
              "confidence boundary: TP53,BAX HTTP")
grade(r, [
    ("lead has supported claims", lambda d: len(d.get("lead_candidate", {}).get("supported_claims", [])) > 0),
    ("lead has unsupported claims", lambda d: len(d.get("lead_candidate", {}).get("unsupported_claims", [])) > 0),
    ("lead has data needed", lambda d: len(d.get("lead_candidate", {}).get("data_needed", [])) > 0),
])
results.append(r)

r = run_skill("grn-confidence-boundary",
              ["--gene-ids", "Peaxi162Scf00118g00310", "--intent", "rnai", "--species", "petunia"],
              "confidence boundary: petunia rnai HTTP")
grade(r, [
    ("has candidate boundaries", lambda d: len(d.get("candidate_boundaries", [])) > 0),
    ("has safe interpretations", lambda d: len(d.get("lead_candidate", {}).get("safe_interpretations", [])) > 0),
])
results.append(r)

# =====================================================================
# GRN-HYPOTHESIS-COMPARE (HTTP)
# =====================================================================
r = run_skill("grn-hypothesis-compare",
              ["--gene-ids", "TP53,MDM2,BAX", "--intent", "experiment"],
              "hypothesis compare: TP53,MDM2,BAX HTTP")
grade(r, [
    ("has winner", lambda d: d.get("winner", {}).get("gene_id") == "TP53"),
    ("has pairwise comparisons", lambda d: len(d.get("pairwise_comparisons", [])) > 0),
    ("has overturn conditions", lambda d: len(d.get("overturn_conditions", [])) > 0),
])
results.append(r)

r = run_skill("grn-hypothesis-compare",
              ["--gene-ids", "Peaxi162Scf00118g00310,Peaxi162Scf00450g00110", "--intent", "rnai", "--species", "petunia"],
              "hypothesis compare: petunia rnai HTTP")
grade(r, [
    ("has comparison table", lambda d: len(d.get("comparison_table", [])) > 0),
    ("has summary", lambda d: len(d.get("summary", [])) > 0),
])
results.append(r)

# =====================================================================
# GRN-RESEARCH-BRIEF (HTTP)
# =====================================================================
r = run_skill("grn-research-brief",
              ["--gene-ids", "TP53,BAX,MDM2", "--intent", "experiment"],
              "research brief: TP53,BAX,MDM2 HTTP")
grade(r, [
    ("has candidate brief", lambda d: len(d.get("candidate_brief", [])) > 0),
    ("has workflow plan", lambda d: len(d.get("workflow_plan", [])) > 0),
    ("has executive summary", lambda d: len(d.get("executive_summary", [])) > 0),
])
results.append(r)

r = run_skill("grn-research-brief",
              ["--gene-ids", "Peaxi162Scf00118g00310", "--intent", "rnai", "--species", "petunia"],
              "research brief: petunia rnai HTTP")
grade(r, [
    ("includes rnai validation step", lambda d: any(step.get("action") == "validate_rnai_design"
                                                     for step in d.get("workflow_plan", []))),
])
results.append(r)

# =====================================================================
# GRN-VALIDATION-PLAN (HTTP)
# =====================================================================
r = run_skill("grn-validation-plan",
              ["--gene-ids", "TP53,BAX,MDM2", "--intent", "experiment"],
              "validation plan: TP53,BAX,MDM2 HTTP")
grade(r, [
    ("has validation tracks", lambda d: len(d.get("validation_tracks", [])) > 0),
    ("has decision gates", lambda d: len(d.get("decision_gates", [])) > 0),
    ("has execution checklist", lambda d: len(d.get("execution_checklist", [])) > 0),
])
results.append(r)

r = run_skill("grn-validation-plan",
              ["--gene-ids", "Peaxi162Scf00118g00310", "--intent", "rnai", "--species", "petunia"],
              "validation plan: petunia rnai HTTP")
grade(r, [
    ("leads with dsrna design", lambda d: d.get("validation_tracks", [{}])[0].get("experiment") == "dsrna_design"),
])
results.append(r)

# =====================================================================
# GRN-STUDY-PACKET (HTTP)
# =====================================================================
r = run_skill("grn-study-packet",
              ["--gene-ids", "TP53,BAX,MDM2", "--intent", "experiment"],
              "study packet: TP53,BAX,MDM2 HTTP")
grade(r, [
    ("has brief", lambda d: "brief" in d),
    ("has validation plan", lambda d: "validation_plan" in d),
    ("has citation bundle", lambda d: len(d.get("citation_bundle", {}).get("sources", [])) > 0),
])
results.append(r)

r = run_skill("grn-study-packet",
              ["--gene-ids", "Peaxi162Scf00118g00310", "--intent", "rnai", "--species", "petunia"],
              "study packet: petunia rnai HTTP")
grade(r, [
    ("handoff has checklist", lambda d: len(d.get("handoff", {}).get("handoff_checklist", [])) > 0),
    ("packet metadata present", lambda d: "packet_metadata" in d),
])
results.append(r)

# =====================================================================
# GRN-STUDY-REPORT (HTTP)
# =====================================================================
r = run_skill("grn-study-report",
              ["--gene-ids", "TP53,BAX,MDM2", "--intent", "experiment"],
              "study report: TP53,BAX,MDM2 HTTP")
grade(r, [
    ("has packet", lambda d: "packet" in d),
    ("has markdown", lambda d: "markdown" in d),
    ("markdown has citations section", lambda d: "## Citations" in d.get("markdown", "")),
])
results.append(r)

r = run_skill("grn-study-report",
              ["--gene-ids", "Peaxi162Scf00118g00310", "--intent", "rnai", "--species", "petunia"],
              "study report: petunia rnai HTTP")
grade(r, [
    ("has report metadata", lambda d: "report_metadata" in d),
    ("markdown has validation section", lambda d: "## Validation status" in d.get("markdown", "")),
])
results.append(r)

# =====================================================================
# REPORT
# =====================================================================
print("=" * 70)
print("GRN ATLAS SKILLS HTTP-MODE TEST REPORT")
print("=" * 70)

pass_count = sum(1 for r in results if r["grade"] == "PASS")
fail_count = sum(1 for r in results if r["grade"] == "FAIL")

skill_stats = {}
for r in results:
    s = r["skill"]
    if s not in skill_stats:
        skill_stats[s] = {"pass": 0, "fail": 0}
    skill_stats[s]["pass" if r["grade"] == "PASS" else "fail"] += 1

print("\n--- Per-Skill Summary ---")
for s in sorted(skill_stats):
    st = skill_stats[s]
    total = st["pass"] + st["fail"]
    icon = "✓" if st["fail"] == 0 else "✗"
    print(f"  {icon} {s}: {st['pass']}/{total}")

failures = [r for r in results if r["grade"] == "FAIL"]
if failures:
    print(f"\n--- Failures ({len(failures)}) ---")
    for r in failures:
        print(f"\n  ✗ {r['skill']}: {r['label']}")
        if r.get("error"):
            print(f"    ERROR: {r['error'][:500]}")
        for c in r.get("checks", []):
            if not c["pass"]:
                print(f"    ✗ {c['check']}")
else:
    print("\n  No failures!")

print(f"\n{'=' * 70}")
print(f"TOTAL: {pass_count} PASS / {fail_count} FAIL / {len(results)} tests")
print(f"{'=' * 70}")

with open(SKILLS_DIR / "_test_results_http.json", "w") as f:
    slim = [{k: v for k, v in r.items() if k != "data"} for r in results]
    json.dump(slim, f, indent=2)

print(f"\nResults saved to _test_results_http.json")
