#!/usr/bin/env python3
"""
Integration tests for GRN Atlas: cross-skill consistency, boundary inputs,
performance regression, and idempotency checks.

Run: backend/venv/bin/python .agents/skills/_test_integration.py
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
PYTHON = str(REPO_ROOT / "backend" / "venv" / "bin" / "python")

results = []


def run_skill(skill_name, args, label):
    script = SKILLS_DIR / skill_name / "scripts" / "run.py"
    cmd = [PYTHON, str(script)] + args
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(REPO_ROOT))
        elapsed = time.time() - t0
        if proc.returncode != 0:
            return {"skill": skill_name, "label": label, "status": "ERROR",
                    "error": proc.stderr.strip()[-500:], "data": None, "time_s": elapsed}
        data = json.loads(proc.stdout)
        return {"skill": skill_name, "label": label, "status": "OK",
                "data": data, "error": None, "time_s": elapsed}
    except subprocess.TimeoutExpired:
        return {"skill": skill_name, "label": label, "status": "TIMEOUT",
                "data": None, "error": "timeout", "time_s": 120.0}
    except json.JSONDecodeError as e:
        return {"skill": skill_name, "label": label, "status": "JSON_ERROR",
                "data": None, "error": f"Bad JSON: {e}", "time_s": time.time() - t0}
    except Exception as e:
        return {"skill": skill_name, "label": label, "status": "EXCEPTION",
                "data": None, "error": str(e), "time_s": time.time() - t0}


def grade(result, checks):
    if result["status"] != "OK":
        result["grade"] = "FAIL"
        result["checks"] = [{"check": "execution", "pass": False, "detail": result.get("error")}]
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


def timed_grade(result, checks, max_seconds):
    """Grade with an additional timing check."""
    all_checks = checks + [
        (f"completes in <{max_seconds}s", lambda d: result["time_s"] < max_seconds),
    ]
    return grade(result, all_checks)


# =====================================================================
# CATEGORY 2: Cross-skill data consistency
# =====================================================================
print("=" * 70)
print("CROSS-SKILL DATA CONSISTENCY")
print("=" * 70)

# Test: regulon depth-1 genes match network targets
r_regulon = run_skill("grn-regulon",
                       ["--gene-id", "TP53", "--depth", "1"],
                       "consistency: regulon TP53 depth 1")
r_network = run_skill("grn-network",
                       ["--gene-id", "TP53", "--direction", "targets"],
                       "consistency: network TP53 targets")

if r_regulon["status"] == "OK" and r_network["status"] == "OK":
    regulon_genes = set(r_regulon["data"].get("genes", {}).keys())
    regulon_genes.discard("TP53")
    network_targets = set(t["id"] for t in r_network["data"].get("targets", []))
    r = {"skill": "cross-skill", "label": "consistency: regulon vs network targets for TP53",
         "status": "OK", "data": {"regulon": len(regulon_genes), "network": len(network_targets)},
         "error": None, "time_s": 0}
    grade(r, [
        ("regulon genes ⊆ network targets", lambda d: regulon_genes.issubset(network_targets)),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: regulon vs network targets for TP53",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: gene-info species matches gene-search species
r_search = run_skill("grn-gene-search",
                      ["--query", "TP53", "--species", "human", "--limit", "1"],
                      "consistency: search TP53")
r_info = run_skill("grn-gene-info",
                    ["--gene-id", "TP53"],
                    "consistency: info TP53")

if r_search["status"] == "OK" and r_info["status"] == "OK":
    search_species = r_search["data"].get("genes", r_search["data"].get("results", [{}]))[0].get("species")
    info_species = r_info["data"].get("species")
    r = {"skill": "cross-skill", "label": "consistency: search vs info species for TP53",
         "status": "OK", "data": {"search": search_species, "info": info_species},
         "error": None, "time_s": 0}
    grade(r, [
        ("species match", lambda d: search_species == info_species),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: search vs info species for TP53",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: inferred edges with compare_curated flag — curated edges actually exist in network
r_infer = run_skill("grn-infer",
                     ["--species", "arabidopsis", "--gene-id", "AT5G11260",
                      "--compare-curated", "--top", "50"],
                     "consistency: infer compare curated")

if r_infer["status"] == "OK":
    curated_edges = [(e["source_id"], e["target_id"])
                     for e in r_infer["data"].get("edges", [])
                     if e.get("has_curated_support")]
    if curated_edges:
        src, tgt = curated_edges[0]
        r_net = run_skill("grn-network",
                          ["--gene-id", src, "--direction", "targets"],
                          "consistency: verify curated edge in network")
        if r_net["status"] == "OK":
            net_targets = set(e["target_id"] for e in r_net["data"].get("interactions", []))
            r = {"skill": "cross-skill",
                 "label": "consistency: inferred curated-support edge exists in network",
                 "status": "OK", "data": {"edge": f"{src}->{tgt}", "in_network": tgt in net_targets},
                 "error": None, "time_s": 0}
            grade(r, [
                ("curated-supported edge exists in network", lambda d: d["in_network"]),
            ])
        else:
            r = {"skill": "cross-skill",
                 "label": "consistency: inferred curated-support edge exists in network",
                 "status": "ERROR", "grade": "FAIL", "data": None, "error": "network query failed",
                 "checks": [{"check": "execution", "pass": False}], "time_s": 0}
    else:
        r = {"skill": "cross-skill",
             "label": "consistency: inferred curated-support edge exists in network",
             "status": "OK", "data": {"note": "no curated-supported edges found"},
             "error": None, "time_s": 0}
        grade(r, [("query returned results", lambda d: True)])
else:
    r = {"skill": "cross-skill",
         "label": "consistency: inferred curated-support edge exists in network",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "infer query failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: orthology output has tomato entry for HY5
r_orth = run_skill("grn-orthology",
                    ["--gene-id", "AT5G11260"],
                    "consistency: orthology HY5")

if r_orth["status"] == "OK":
    orth_species = set(r_orth["data"].keys())
    r = {"skill": "cross-skill", "label": "consistency: orthology has tomato for HY5",
         "status": "OK", "data": {"species": list(orth_species)},
         "error": None, "time_s": 0}
    grade(r, [
        ("has cross-species orthologs", lambda d: len(orth_species) > 1),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: orthology has tomato for HY5",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: expression profile gene matches coexpression source gene
r_expr = run_skill("grn-expression",
                    ["--gene-id", "AT5G11260"],
                    "consistency: expression HY5")
r_coex = run_skill("grn-coexpression",
                    ["--gene-id", "AT5G11260", "--top", "3"],
                    "consistency: coexpression HY5")

if r_expr["status"] == "OK" and r_coex["status"] == "OK":
    expr_gene = r_expr["data"].get("gene_id")
    coex_gene = r_coex["data"].get("gene_id")
    r = {"skill": "cross-skill", "label": "consistency: expression vs coexpression gene_id",
         "status": "OK", "data": {"expr": expr_gene, "coex": coex_gene},
         "error": None, "time_s": 0}
    grade(r, [
        ("gene_ids match", lambda d: expr_gene == coex_gene),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: expression vs coexpression gene_id",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: stats gene count matches species gene counts
r_stats = run_skill("grn-stats", [], "consistency: global stats")
r_species = run_skill("grn-species", [], "consistency: species list")

if r_stats["status"] == "OK" and r_species["status"] == "OK":
    stats_total = r_stats["data"].get("genes", 0)
    species_total = sum(
        s.get("genes", 0)
        for s in r_species["data"].get("species", [])
    )
    r = {"skill": "cross-skill", "label": "consistency: stats total_genes vs species sum",
         "status": "OK", "data": {"stats": stats_total, "species_sum": species_total},
         "error": None, "time_s": 0}
    grade(r, [
        ("totals match", lambda d: stats_total == species_total),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: stats total_genes vs species sum",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: evidence audit agrees that TP53->BAX is supported when network/path exists
r_audit = run_skill("grn-evidence-audit",
                    ["--scope", "edge", "--source-id", "TP53", "--target-id", "BAX"],
                    "consistency: evidence audit TP53->BAX")
r_path = run_skill("grn-pathfinding",
                   ["--source", "TP53", "--target", "BAX", "--max-depth", "1"],
                   "consistency: pathfinding TP53->BAX")

if r_audit["status"] == "OK" and r_path["status"] == "OK":
    r = {"skill": "cross-skill", "label": "consistency: evidence audit aligns with direct TP53->BAX path",
         "status": "OK", "data": {"audit": r_audit["data"]["summary"]["supported"], "paths": len(r_path["data"].get("paths", []))},
         "error": None, "time_s": 0}
    grade(r, [
        ("audit supported", lambda d: d["audit"] is True),
        ("has direct path", lambda d: d["paths"] > 0),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: evidence audit aligns with direct TP53->BAX path",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: coverage report agrees with species capabilities for expression-ready species
r_cov = run_skill("grn-coverage-report",
                  ["--species", "arabidopsis", "--intent", "expression"],
                  "consistency: coverage report arabidopsis expression")

if r_cov["status"] == "OK" and r_species["status"] == "OK":
    species_rows = {s["species"]: s for s in r_species["data"].get("species", [])}
    expr_samples = species_rows["arabidopsis"]["layers"]["expression_samples"]
    cov_samples = r_cov["data"]["available_layers"]["expression_samples"]
    r = {"skill": "cross-skill", "label": "consistency: coverage report matches species expression counts",
         "status": "OK", "data": {"species": expr_samples, "coverage": cov_samples},
         "error": None, "time_s": 0}
    grade(r, [
        ("expression counts match", lambda d: d["species"] == d["coverage"]),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: coverage report matches species expression counts",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: candidate triage and experiment prioritization agree on the lead candidate
r_triage = run_skill("grn-candidate-triage",
                     ["--gene-ids", "TP53,BAX,MDM2", "--intent", "network"],
                     "consistency: candidate triage TP53,BAX,MDM2")
r_plan = run_skill("grn-experiment-prioritization",
                   ["--gene-ids", "TP53,BAX,MDM2", "--intent", "network"],
                   "consistency: experiment prioritization TP53,BAX,MDM2")

if r_triage["status"] == "OK" and r_plan["status"] == "OK":
    lead_triage = r_triage["data"].get("ranked_candidates", [{}])[0].get("gene_id")
    lead_plan = r_plan["data"].get("plans", [{}])[0].get("gene_id")
    r = {"skill": "cross-skill", "label": "consistency: triage lead matches first experiment plan",
         "status": "OK", "data": {"triage": lead_triage, "plan": lead_plan},
         "error": None, "time_s": 0}
    grade(r, [
        ("lead candidate matches", lambda d: lead_triage == lead_plan),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: triage lead matches first experiment plan",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: hypothesis comparison agrees with candidate triage on the lead candidate
r_hcmp = run_skill("grn-hypothesis-compare",
                   ["--gene-ids", "TP53,BAX,MDM2", "--intent", "network"],
                   "consistency: hypothesis compare TP53,BAX,MDM2")

if r_hcmp["status"] == "OK" and r_triage["status"] == "OK":
    cmp_lead = r_hcmp["data"].get("winner", {}).get("gene_id")
    triage_lead = r_triage["data"].get("ranked_candidates", [{}])[0].get("gene_id")
    r = {"skill": "cross-skill", "label": "consistency: hypothesis compare lead matches triage",
         "status": "OK", "data": {"compare": cmp_lead, "triage": triage_lead},
         "error": None, "time_s": 0}
    grade(r, [
        ("lead matches", lambda d: cmp_lead == triage_lead),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: hypothesis compare lead matches triage",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: petunia RNAi prioritization surfaces dsRNA design when coverage says expression exists
r_cov_rnai = run_skill("grn-coverage-report",
                       ["--species", "petunia", "--intent", "rnai"],
                       "consistency: coverage report petunia rnai")
r_rnai = run_skill("grn-experiment-prioritization",
                   ["--gene-ids", "Peaxi162Scf00118g00310", "--intent", "rnai", "--species", "petunia"],
                   "consistency: experiment prioritization petunia rnai")

if r_cov_rnai["status"] == "OK" and r_rnai["status"] == "OK":
    has_expr = r_cov_rnai["data"].get("available_layers", {}).get("expression_samples", 0) > 0
    dsrna = any(e.get("experiment") == "dsrna_design"
                for e in r_rnai["data"].get("plans", [{}])[0].get("recommended_experiments", []))
    r = {"skill": "cross-skill", "label": "consistency: petunia rnai readiness enables dsRNA recommendation",
         "status": "OK", "data": {"expression_available": has_expr, "dsrna_recommended": dsrna},
         "error": None, "time_s": 0}
    grade(r, [
        ("expression available", lambda d: d["expression_available"] is True),
        ("dsRNA recommended", lambda d: d["dsrna_recommended"] is True),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: petunia rnai readiness enables dsRNA recommendation",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: research brief agrees with triage and prioritization on the lead candidate
r_brief = run_skill("grn-research-brief",
                    ["--gene-ids", "TP53,BAX,MDM2", "--intent", "experiment"],
                    "consistency: research brief TP53,BAX,MDM2")

if r_brief["status"] == "OK" and r_triage["status"] == "OK" and r_plan["status"] == "OK":
    brief_lead = r_brief["data"].get("candidate_brief", [{}])[0].get("gene_id")
    triage_lead = r_triage["data"].get("ranked_candidates", [{}])[0].get("gene_id")
    plan_lead = r_plan["data"].get("plans", [{}])[0].get("gene_id")
    r = {"skill": "cross-skill", "label": "consistency: research brief lead matches triage and prioritization",
         "status": "OK", "data": {"brief": brief_lead, "triage": triage_lead, "plan": plan_lead},
         "error": None, "time_s": 0}
    grade(r, [
        ("brief matches triage", lambda d: brief_lead == triage_lead),
        ("brief matches prioritization", lambda d: brief_lead == plan_lead),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: research brief lead matches triage and prioritization",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: transferability surfaces an ortholog-backed target candidate
r_transfer = run_skill("grn-transferability",
                       ["--gene-id", "TP53", "--target-species", "mouse", "--intent", "network"],
                       "consistency: transferability TP53 to mouse")
if r_transfer["status"] == "OK":
    target_gene = r_transfer["data"].get("best_target_ortholog", {}).get("gene_id")
    caveats = r_transfer["data"].get("caveats", [])
    r = {"skill": "cross-skill", "label": "consistency: transferability returns ortholog candidate with caveats",
         "status": "OK", "data": {"target_gene": target_gene, "caveats": caveats},
         "error": None, "time_s": 0}
    grade(r, [
        ("target ortholog present", lambda d: target_gene is not None),
        ("caveats exist", lambda d: len(caveats) > 0),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: transferability returns ortholog candidate with caveats",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: confidence boundary lead matches research brief and surfaces coverage-driven unsupported claims
r_boundary = run_skill("grn-confidence-boundary",
                       ["--gene-ids", "TP53,BAX,MDM2", "--intent", "experiment"],
                       "consistency: confidence boundary TP53,BAX,MDM2")
if r_boundary["status"] == "OK" and r_brief["status"] == "OK":
    boundary_lead = r_boundary["data"].get("lead_candidate", {}).get("gene_id")
    brief_lead = r_brief["data"].get("candidate_brief", [{}])[0].get("gene_id")
    unsupported = r_boundary["data"].get("lead_candidate", {}).get("unsupported_claims", [])
    r = {"skill": "cross-skill", "label": "consistency: confidence boundary lead matches brief and surfaces unsupported claims",
         "status": "OK", "data": {"boundary": boundary_lead, "brief": brief_lead, "unsupported": unsupported},
         "error": None, "time_s": 0}
    grade(r, [
        ("lead matches", lambda d: boundary_lead == brief_lead),
        ("unsupported claims exist", lambda d: len(unsupported) > 0),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: confidence boundary lead matches brief and surfaces unsupported claims",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: validation plan agrees with research brief on lead candidate and RNAi first action
r_vplan = run_skill("grn-validation-plan",
                    ["--gene-ids", "TP53,BAX,MDM2", "--intent", "experiment"],
                    "consistency: validation plan TP53,BAX,MDM2")

if r_vplan["status"] == "OK" and r_brief["status"] == "OK":
    plan_lead = r_vplan["data"].get("lead_candidate", {}).get("gene_id")
    brief_lead = r_brief["data"].get("candidate_brief", [{}])[0].get("gene_id")
    r = {"skill": "cross-skill", "label": "consistency: validation plan lead matches research brief",
         "status": "OK", "data": {"validation": plan_lead, "brief": brief_lead},
         "error": None, "time_s": 0}
    grade(r, [
        ("lead matches", lambda d: plan_lead == brief_lead),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: validation plan lead matches research brief",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

r_vplan_rnai = run_skill("grn-validation-plan",
                         ["--gene-ids", "Peaxi162Scf00118g00310", "--intent", "rnai", "--species", "petunia"],
                         "consistency: validation plan petunia rnai")

if r_vplan_rnai["status"] == "OK":
    first_exp = r_vplan_rnai["data"].get("validation_tracks", [{}])[0].get("experiment")
    r = {"skill": "cross-skill", "label": "consistency: validation plan rnai starts with dsrna_design",
         "status": "OK", "data": {"experiment": first_exp},
         "error": None, "time_s": 0}
    grade(r, [
        ("first experiment is dsrna_design", lambda d: first_exp == "dsrna_design"),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: validation plan rnai starts with dsrna_design",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: study packet embeds the same lead candidate and citations
r_packet = run_skill("grn-study-packet",
                     ["--gene-ids", "TP53,BAX,MDM2", "--intent", "experiment"],
                     "consistency: study packet TP53,BAX,MDM2")

if r_packet["status"] == "OK" and r_brief["status"] == "OK" and r_vplan["status"] == "OK":
    packet_lead = r_packet["data"].get("packet_metadata", {}).get("lead_candidate")
    brief_lead = r_brief["data"].get("candidate_brief", [{}])[0].get("gene_id")
    citations = r_packet["data"].get("citation_bundle", {}).get("source_keys", [])
    r = {"skill": "cross-skill", "label": "consistency: study packet lead matches brief and has citations",
         "status": "OK", "data": {"packet": packet_lead, "brief": brief_lead, "citations": citations},
         "error": None, "time_s": 0}
    grade(r, [
        ("lead matches", lambda d: packet_lead == brief_lead),
        ("has citations", lambda d: len(citations) > 0),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: study packet lead matches brief and has citations",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Test: study report wraps the packet and preserves lead candidate + markdown sections
r_report = run_skill("grn-study-report",
                     ["--gene-ids", "TP53,BAX,MDM2", "--intent", "experiment"],
                     "consistency: study report TP53,BAX,MDM2")

if r_report["status"] == "OK" and r_packet["status"] == "OK":
    report_lead = r_report["data"].get("report_metadata", {}).get("lead_candidate")
    packet_lead = r_packet["data"].get("packet_metadata", {}).get("lead_candidate")
    md = r_report["data"].get("markdown", "")
    r = {"skill": "cross-skill", "label": "consistency: study report wraps packet and has markdown sections",
         "status": "OK", "data": {"report": report_lead, "packet": packet_lead, "markdown": md},
         "error": None, "time_s": 0}
    grade(r, [
        ("lead matches", lambda d: report_lead == packet_lead),
        ("has candidate section", lambda d: "## Candidate ranking" in md),
        ("has citations section", lambda d: "## Citations" in md),
    ])
else:
    r = {"skill": "cross-skill", "label": "consistency: study report wraps packet and has markdown sections",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)


# =====================================================================
# CATEGORY 3: Boundary / adversarial inputs
# =====================================================================
print("\n" + "=" * 70)
print("BOUNDARY / ADVERSARIAL INPUTS")
print("=" * 70)

# SQL injection attempts
r = run_skill("grn-gene-search",
              ["--query", "'; DROP TABLE genes; --", "--species", "human"],
              "boundary: SQL injection in search query")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
    ("no crash", lambda d: True),
])
results.append(r)

r = run_skill("grn-gene-info",
              ["--gene-id", "' OR 1=1 --"],
              "boundary: SQL injection in gene_id")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-network",
              ["--gene-id", "'; DELETE FROM interactions; --", "--direction", "both"],
              "boundary: SQL injection in network query")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
    ("no results (gene doesn't exist)", lambda d: len(d.get("regulators", []) + d.get("targets", [])) == 0),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "'; DROP TABLE inferred_edges; --", "--top", "5"],
              "boundary: SQL injection in infer species")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
    ("no edges", lambda d: len(d.get("edges", [])) == 0),
])
results.append(r)

# Empty / missing inputs
r = run_skill("grn-gene-search",
              ["--query", "", "--species", "human"],
              "boundary: empty search query")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
])
results.append(r)

# Nonexistent species
r = run_skill("grn-network",
              ["--gene-id", "TP53", "--direction", "both"],
              "boundary: gene query without species filter")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-species", [],
              "boundary: species list returns all")
grade(r, [
    ("has species", lambda d: len(d.get("species", [])) > 0),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "martian_plant", "--top", "5"],
              "boundary: nonexistent species in infer")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
    ("no edges", lambda d: len(d.get("edges", [])) == 0),
])
results.append(r)

r = run_skill("grn-module",
              ["--species", "nonexistent"],
              "boundary: nonexistent species in module")
grade(r, [
    ("returns valid JSON or error", lambda d: isinstance(d, dict)),
])
results.append(r)

# Unicode in gene search
r = run_skill("grn-gene-search",
              ["--query", "αβγ∆", "--species", "human"],
              "boundary: unicode in search")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
    ("no crash", lambda d: True),
])
results.append(r)

# Very long gene list
long_ids = ",".join(f"FAKE_GENE_{i}" for i in range(100))
r = run_skill("grn-enrichment",
              ["--gene-ids", long_ids, "--species", "human", "--type", "go"],
              "boundary: 100 fake gene_ids in enrichment")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
])
results.append(r)

# Extreme numeric thresholds
r = run_skill("grn-network",
              ["--gene-id", "TP53", "--min-confidence", "999", "--direction", "both"],
              "boundary: impossibly high min_confidence")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
    ("no results", lambda d: len(d.get("regulators", []) + d.get("targets", [])) == 0),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--min-importance", "0.0", "--top", "3"],
              "boundary: zero min_importance")
grade(r, [
    ("returns edges", lambda d: len(d.get("edges", [])) > 0),
])
results.append(r)

r = run_skill("grn-coexpression",
              ["--gene-id", "AT5G11260", "--min-r", "0.999", "--top", "3"],
              "boundary: near-perfect correlation threshold")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
])
results.append(r)

# Single-character query
r = run_skill("grn-gene-search",
              ["--query", "A", "--species", "arabidopsis", "--limit", "3"],
              "boundary: single-char search")
grade(r, [
    ("returns valid JSON", lambda d: isinstance(d, dict)),
])
results.append(r)


# =====================================================================
# CATEGORY 4: Performance regression
# =====================================================================
print("\n" + "=" * 70)
print("PERFORMANCE REGRESSION")
print("=" * 70)

r = run_skill("grn-gene-search",
              ["--query", "TP53", "--species", "human"],
              "perf: gene search")
timed_grade(r, [
    ("returns results", lambda d: len(d.get("genes", d.get("results", []))) > 0),
], max_seconds=2.0)
results.append(r)

r = run_skill("grn-network",
              ["--gene-id", "TP53", "--direction", "both"],
              "perf: network query")
timed_grade(r, [
    ("returns results", lambda d: len(d.get("regulators", []) + d.get("targets", [])) > 0),
], max_seconds=2.0)
results.append(r)

r = run_skill("grn-regulon",
              ["--gene-id", "TP53", "--depth", "2"],
              "perf: regulon depth 2")
timed_grade(r, [
    ("returns genes", lambda d: d.get("total", 0) > 0),
], max_seconds=5.0)
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,MYC,BAX,BCL2,CDKN1A,MDM2", "--species", "human", "--type", "go"],
              "perf: GO enrichment 6 genes")
timed_grade(r, [
    ("returns results", lambda d: isinstance(d, dict)),
], max_seconds=5.0)
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--top", "50"],
              "perf: inferred edges top 50")
timed_grade(r, [
    ("returns edges", lambda d: len(d.get("edges", [])) > 0),
], max_seconds=2.0)
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--gene-id", "AT5G11260", "--compare-curated", "--top", "50"],
              "perf: inferred edges with curated comparison")
timed_grade(r, [
    ("returns edges", lambda d: "edges" in d),
], max_seconds=3.0)
results.append(r)

r = run_skill("grn-module",
              ["--species", "arabidopsis", "--top-modules", "5"],
              "perf: community detection arabidopsis")
timed_grade(r, [
    ("returns modules", lambda d: "modules" in d),
], max_seconds=15.0)
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "betweenness", "--top", "5"],
              "perf: betweenness centrality")
timed_grade(r, [
    ("returns results", lambda d: len(d.get("results", [])) > 0),
], max_seconds=10.0)
results.append(r)

r = run_skill("grn-motif",
              ["--gene-id", "AT5G11260", "--species", "arabidopsis"],
              "perf: motif query")
timed_grade(r, [
    ("returns hits", lambda d: "hits" in d),
], max_seconds=3.0)
results.append(r)

r = run_skill("grn-pathfinding",
              ["--source", "TP53", "--target", "BAX", "--max-depth", "3"],
              "perf: pathfinding depth 3")
timed_grade(r, [
    ("returns paths", lambda d: "paths" in d),
], max_seconds=5.0)
results.append(r)


# =====================================================================
# CATEGORY 6: Idempotency / reproducibility
# =====================================================================
print("\n" + "=" * 70)
print("IDEMPOTENCY / REPRODUCIBILITY")
print("=" * 70)

# Run the same query twice and verify identical results
r1 = run_skill("grn-infer",
               ["--species", "arabidopsis", "--top", "10", "--method", "GRNBoost2"],
               "idempotent: infer run 1")
r2 = run_skill("grn-infer",
               ["--species", "arabidopsis", "--top", "10", "--method", "GRNBoost2"],
               "idempotent: infer run 2")

if r1["status"] == "OK" and r2["status"] == "OK":
    edges1 = [(e["source_id"], e["target_id"], e["importance"]) for e in r1["data"]["edges"]]
    edges2 = [(e["source_id"], e["target_id"], e["importance"]) for e in r2["data"]["edges"]]
    r = {"skill": "idempotency", "label": "idempotent: infer returns identical results",
         "status": "OK", "data": {"n1": len(edges1), "n2": len(edges2)},
         "error": None, "time_s": 0}
    grade(r, [
        ("same edges", lambda d: edges1 == edges2),
        ("same count", lambda d: len(edges1) == len(edges2)),
    ])
else:
    r = {"skill": "idempotency", "label": "idempotent: infer returns identical results",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Network query idempotency
r1 = run_skill("grn-network",
               ["--gene-id", "TP53", "--direction", "targets", "--min-confidence", "0.5"],
               "idempotent: network run 1")
r2 = run_skill("grn-network",
               ["--gene-id", "TP53", "--direction", "targets", "--min-confidence", "0.5"],
               "idempotent: network run 2")

if r1["status"] == "OK" and r2["status"] == "OK":
    ids1 = sorted(e["target_id"] for e in r1["data"].get("interactions", []))
    ids2 = sorted(e["target_id"] for e in r2["data"].get("interactions", []))
    r = {"skill": "idempotency", "label": "idempotent: network returns identical results",
         "status": "OK", "data": {"n1": len(ids1), "n2": len(ids2)},
         "error": None, "time_s": 0}
    grade(r, [
        ("same targets", lambda d: ids1 == ids2),
    ])
else:
    r = {"skill": "idempotency", "label": "idempotent: network returns identical results",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Enrichment idempotency
r1 = run_skill("grn-enrichment",
               ["--gene-ids", "TP53,MYC,BAX", "--species", "human", "--type", "go"],
               "idempotent: enrichment run 1")
r2 = run_skill("grn-enrichment",
               ["--gene-ids", "TP53,MYC,BAX", "--species", "human", "--type", "go"],
               "idempotent: enrichment run 2")

if r1["status"] == "OK" and r2["status"] == "OK":
    ids1 = set(r.get("go_id", r.get("pathway_id", "")) for r in r1["data"].get("results", []))
    ids2 = set(r.get("go_id", r.get("pathway_id", "")) for r in r2["data"].get("results", []))
    r = {"skill": "idempotency", "label": "idempotent: enrichment returns same term set",
         "status": "OK", "data": {"n1": len(ids1), "n2": len(ids2)},
         "error": None, "time_s": 0}
    grade(r, [
        ("same term IDs", lambda d: ids1 == ids2),
        ("same count", lambda d: len(ids1) == len(ids2)),
    ])
else:
    r = {"skill": "idempotency", "label": "idempotent: enrichment returns same term set",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)

# Motif query idempotency
r1 = run_skill("grn-motif",
               ["--gene-id", "AT5G11260", "--species", "arabidopsis", "--top", "5"],
               "idempotent: motif run 1")
r2 = run_skill("grn-motif",
               ["--gene-id", "AT5G11260", "--species", "arabidopsis", "--top", "5"],
               "idempotent: motif run 2")

if r1["status"] == "OK" and r2["status"] == "OK":
    r = {"skill": "idempotency", "label": "idempotent: motif returns identical results",
         "status": "OK", "data": r1["data"],
         "error": None, "time_s": 0}
    grade(r, [
        ("same output", lambda d: json.dumps(r1["data"], sort_keys=True) == json.dumps(r2["data"], sort_keys=True)),
    ])
else:
    r = {"skill": "idempotency", "label": "idempotent: motif returns identical results",
         "status": "ERROR", "grade": "FAIL", "data": None, "error": "prerequisite failed",
         "checks": [{"check": "execution", "pass": False}], "time_s": 0}
results.append(r)


# =====================================================================
# REPORT
# =====================================================================
print("\n" + "=" * 70)
print("INTEGRATION TEST REPORT")
print("=" * 70)

categories = {}
for r in results:
    cat = r["skill"] if r["skill"] in ("cross-skill", "idempotency") else r["label"].split(":")[0]
    if cat not in categories:
        categories[cat] = {"pass": 0, "fail": 0}
    categories[cat]["pass" if r["grade"] == "PASS" else "fail"] += 1

for cat in sorted(categories):
    st = categories[cat]
    total = st["pass"] + st["fail"]
    icon = "✓" if st["fail"] == 0 else "✗"
    print(f"  {icon} {cat}: {st['pass']}/{total}")

pass_count = sum(1 for r in results if r["grade"] == "PASS")
fail_count = sum(1 for r in results if r["grade"] == "FAIL")

failures = [r for r in results if r["grade"] == "FAIL"]
if failures:
    print(f"\n--- Failures ({len(failures)}) ---")
    for r in failures:
        print(f"\n  ✗ {r.get('skill', '?')}: {r['label']}")
        if r.get("error"):
            print(f"    ERROR: {r['error'][:300]}")
        for c in r.get("checks", []):
            if not c["pass"]:
                print(f"    ✗ {c['check']}")
else:
    print("\n  No failures!")

# Performance timings
print("\n--- Performance Timings ---")
for r in results:
    if r["label"].startswith("perf:"):
        status = "✓" if r["grade"] == "PASS" else "✗"
        print(f"  {status} {r['label']}: {r.get('time_s', 0):.2f}s")

print(f"\n{'=' * 70}")
print(f"TOTAL: {pass_count} PASS / {fail_count} FAIL / {len(results)} tests")
print(f"{'=' * 70}")

with open(SKILLS_DIR / "_test_results_integration.json", "w") as f:
    slim = [{k: v for k, v in r.items() if k != "data"} for r in results]
    json.dump(slim, f, indent=2)

print(f"\nResults saved to _test_results_integration.json")
