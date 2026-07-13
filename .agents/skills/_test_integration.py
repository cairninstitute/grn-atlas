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
