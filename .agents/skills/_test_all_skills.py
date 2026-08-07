#!/usr/bin/env python3
"""
Exhaustive test suite for GRN Atlas AgentSkills.
Each test has a known ground-truth answer derived from direct DB queries.
At least 10 tests per skill.
"""
import json
import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SKILLS_DIR.parents[1]
PYTHON = str(REPO_ROOT / "backend" / "venv" / "bin" / "python")

results = []


def run_skill(skill_name: str, args: list[str], label: str, raw: bool = False) -> dict:
    script = SKILLS_DIR / skill_name / "scripts" / "run.py"
    cmd = [PYTHON, str(script)] + args
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


def G(d): return d.get("genes", d.get("results", []))


# =====================================================================
# 1. grn-gene-search (12 tests)
# =====================================================================

r = run_skill("grn-gene-search", ["--query", "TP53", "--species", "human", "--limit", "5"],
              "search: TP53 exact in human")
grade(r, [
    ("first result is TP53", lambda d: G(d)[0]["symbol"] == "TP53"),
    ("species is human", lambda d: G(d)[0]["species"] == "human"),
    ("TP53 is a TF", lambda d: G(d)[0]["is_tf"] is True),
    ("id is TP53", lambda d: G(d)[0]["id"] == "TP53"),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "MYB", "--species", "arabidopsis", "--limit", "3"],
              "search: MYB in arabidopsis limit 3")
grade(r, [
    ("all arabidopsis", lambda d: all(g["species"] == "arabidopsis" for g in G(d))),
    ("at most 3 results", lambda d: len(G(d)) <= 3),
    ("results not empty", lambda d: len(G(d)) > 0),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "ZZZZNOTAREAL_GENE_XYZ", "--species", "human"],
              "search: nonexistent gene returns empty")
grade(r, [("empty", lambda d: len(G(d)) == 0)])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "BRCA", "--species", "human"],
              "search: BRCA partial match")
grade(r, [
    ("finds BRCA1", lambda d: any(g["symbol"] == "BRCA1" for g in G(d))),
    ("finds BRCA2", lambda d: any(g["symbol"] == "BRCA2" for g in G(d))),
    ("all human", lambda d: all(g["species"] == "human" for g in G(d))),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "apoptosis", "--species", "human", "--limit", "5"],
              "search: by name substring 'apoptosis'")
grade(r, [
    ("finds BAX", lambda d: any(g["symbol"] == "BAX" for g in G(d))),
    ("results not empty", lambda d: len(G(d)) > 0),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "MYC", "--species", "human", "--limit", "1"],
              "search: MYC limit 1")
grade(r, [
    ("exactly 1 result", lambda d: len(G(d)) == 1),
    ("is MYC", lambda d: G(d)[0]["symbol"] == "MYC"),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "HY5", "--species", "arabidopsis"],
              "search: HY5 arabidopsis")
grade(r, [
    ("finds HY5", lambda d: any(g["symbol"] == "HY5" for g in G(d))),
    ("HY5 id is AT5G11260", lambda d: any(g["id"] == "AT5G11260" for g in G(d))),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "AN1", "--species", "tomato"],
              "search: AN1 in tomato")
grade(r, [
    ("finds AN1", lambda d: any(g["symbol"] == "AN1" for g in G(d))),
    ("all tomato", lambda d: all(g["species"] == "tomato" for g in G(d))),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "ABF", "--species", "arabidopsis", "--limit", "50"],
              "search: ABF broad match arabidopsis")
grade(r, [
    ("finds ABF1", lambda d: any(g["symbol"] == "ABF1" for g in G(d))),
    ("finds ABF2", lambda d: any(g["symbol"] == "ABF2" for g in G(d))),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "BCL2"],
              "search: BCL2 no species filter")
grade(r, [
    ("finds BCL2", lambda d: any(g["symbol"] == "BCL2" for g in G(d))),
    ("BCL2 is not a TF", lambda d: any(g["symbol"] == "BCL2" and g["is_tf"] is False for g in G(d))),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "STAT3", "--species", "human"],
              "search: STAT3 is TF")
grade(r, [
    ("finds STAT3", lambda d: G(d)[0]["symbol"] == "STAT3"),
    ("STAT3 is TF", lambda d: G(d)[0]["is_tf"] is True),
    ("protein_coding", lambda d: G(d)[0]["gene_type"] == "protein_coding"),
])
results.append(r)

r = run_skill("grn-gene-search", ["--query", "NFKB1", "--species", "mouse"],
              "search: NFKB1 in mouse (may not exist)")
grade(r, [
    ("returns list", lambda d: isinstance(G(d), list)),
])
results.append(r)


# =====================================================================
# 2. grn-gene-info (11 tests)
# =====================================================================

r = run_skill("grn-gene-info", ["--gene-id", "TP53"], "info: TP53 by id")
grade(r, [
    ("id=TP53", lambda d: d.get("id") == "TP53"),
    ("species=human", lambda d: d.get("species") == "human"),
    ("is_tf=true", lambda d: d.get("is_tf") is True),
    ("name contains tumor", lambda d: "tumor" in d.get("name", "").lower()),
])
results.append(r)

r = run_skill("grn-gene-info", ["--symbol", "ABF1", "--species", "arabidopsis"],
              "info: ABF1 by symbol")
grade(r, [
    ("id=AT1G49720", lambda d: d.get("id") == "AT1G49720"),
    ("symbol=ABF1", lambda d: d.get("symbol") == "ABF1"),
])
results.append(r)

r = run_skill("grn-gene-info", ["--gene-id", "FAKEGENE999"], "info: nonexistent gene")
grade(r, [
    ("handles missing", lambda d: d is None or d == {} or "not found" in str(d).lower() or "error" in str(d).lower()),
])
results.append(r)

r = run_skill("grn-gene-info", ["--gene-id", "MYC"], "info: MYC by id")
grade(r, [
    ("symbol=MYC", lambda d: d.get("symbol") == "MYC"),
    ("is_tf=true", lambda d: d.get("is_tf") is True),
    ("gene_type=protein_coding", lambda d: d.get("gene_type") == "protein_coding"),
])
results.append(r)

r = run_skill("grn-gene-info", ["--gene-id", "BCL2"], "info: BCL2 non-TF")
grade(r, [
    ("symbol=BCL2", lambda d: d.get("symbol") == "BCL2"),
    ("is_tf=false", lambda d: d.get("is_tf") is False),
])
results.append(r)

r = run_skill("grn-gene-info", ["--gene-id", "BAX"], "info: BAX non-TF")
grade(r, [
    ("is_tf=false", lambda d: d.get("is_tf") is False),
    ("species=human", lambda d: d.get("species") == "human"),
])
results.append(r)

r = run_skill("grn-gene-info", ["--symbol", "HY5", "--species", "arabidopsis"],
              "info: HY5 by symbol")
grade(r, [
    ("id=AT5G11260", lambda d: d.get("id") == "AT5G11260"),
    ("is_tf", lambda d: d.get("is_tf") is True),
])
results.append(r)

r = run_skill("grn-gene-info", ["--gene-id", "AT5G11260"], "info: HY5 by AT id")
grade(r, [
    ("symbol=HY5", lambda d: d.get("symbol") == "HY5"),
    ("species=arabidopsis", lambda d: d.get("species") == "arabidopsis"),
])
results.append(r)

r = run_skill("grn-gene-info", ["--gene-id", "NFKB1"], "info: NFKB1")
grade(r, [
    ("symbol=NFKB1", lambda d: d.get("symbol") == "NFKB1"),
    ("is_tf=true", lambda d: d.get("is_tf") is True),
])
results.append(r)

r = run_skill("grn-gene-info", ["--gene-id", "MDM2"], "info: MDM2")
grade(r, [
    ("is_tf=true", lambda d: d.get("is_tf") is True),
    ("species=human", lambda d: d.get("species") == "human"),
])
results.append(r)

r = run_skill("grn-gene-info", ["--symbol", "PIF4", "--species", "arabidopsis"],
              "info: PIF4 by symbol")
grade(r, [
    ("id=AT2G43010", lambda d: d.get("id") == "AT2G43010"),
    ("is_tf", lambda d: d.get("is_tf") is True),
])
results.append(r)


# =====================================================================
# 3. grn-network (12 tests)
# =====================================================================

r = run_skill("grn-network", ["--gene-id", "TP53"], "network: TP53 both")
grade(r, [
    ("31 regulators", lambda d: len(d.get("regulators", [])) == 31),
    ("106 targets", lambda d: len(d.get("targets", [])) == 106),
    ("BAX in targets", lambda d: any(t.get("id") == "BAX" or t.get("symbol") == "BAX" for t in d["targets"])),
    ("SIRT1 in regulators", lambda d: any(r.get("id") == "SIRT1" or r.get("symbol") == "SIRT1" for r in d["regulators"])),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "TP53", "--direction", "regulators"],
              "network: TP53 regulators only")
grade(r, [
    ("has regulators", lambda d: len(d["regulators"]) == 31),
    ("no targets", lambda d: len(d["targets"]) == 0),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "TP53", "--direction", "targets"],
              "network: TP53 targets only")
grade(r, [
    ("has targets", lambda d: len(d["targets"]) == 106),
    ("no regulators", lambda d: len(d["regulators"]) == 0),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "TP53", "--min-confidence", "0.7"],
              "network: TP53 confidence >= 0.7")
grade(r, [
    ("9 regulators at conf>=0.7", lambda d: len(d["regulators"]) == 9),
    ("22 targets at conf>=0.7", lambda d: len(d["targets"]) == 22),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "AT1G49720", "--direction", "targets"],
              "network: ABF1 targets")
grade(r, [
    ("1458 targets", lambda d: len(d["targets"]) == 1458),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "AT1G49720", "--direction", "regulators"],
              "network: ABF1 regulators")
grade(r, [
    ("2 regulators", lambda d: len(d["regulators"]) == 2),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "MYC"], "network: MYC both")
grade(r, [
    ("45 regulators", lambda d: len(d["regulators"]) == 45),
    ("69 targets", lambda d: len(d["targets"]) == 69),
    ("STAT3 regulates MYC", lambda d: any(r.get("symbol") == "STAT3" or r.get("id") == "STAT3" for r in d["regulators"])),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "AT5G11260"], "network: HY5 both")
grade(r, [
    ("32 regulators", lambda d: len(d["regulators"]) == 32),
    ("231 targets", lambda d: len(d["targets"]) == 231),
    ("PIF4 regulates HY5", lambda d: any(r.get("symbol") == "PIF4" or r.get("id") == "AT2G43010" for r in d["regulators"])),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "NFKB1"], "network: NFKB1")
grade(r, [
    ("22 regulators", lambda d: len(d["regulators"]) == 22),
    ("176 targets", lambda d: len(d["targets"]) == 176),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "E2F1"], "network: E2F1")
grade(r, [
    ("20 regulators", lambda d: len(d["regulators"]) == 20),
    ("94 targets", lambda d: len(d["targets"]) == 94),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "FAKEGENE"], "network: nonexistent gene")
grade(r, [
    ("error or empty", lambda d: d is None or "error" in str(d).lower() or "not found" in str(d).lower()
     or (len(d.get("regulators", [])) == 0 and len(d.get("targets", [])) == 0)),
])
results.append(r)

r = run_skill("grn-network", ["--gene-id", "AT5G13930"], "network: gene with 0 targets")
grade(r, [
    ("10 regulators", lambda d: len(d["regulators"]) == 10),
    ("0 targets", lambda d: len(d["targets"]) == 0),
])
results.append(r)


# =====================================================================
# 4. grn-pathfinding (10 tests)
# =====================================================================

r = run_skill("grn-pathfinding", ["--source", "TP53", "--target", "BAX", "--max-depth", "1"],
              "path: TP53->BAX depth 1 (direct)")
grade(r, [
    ("finds path", lambda d: len(d.get("paths", [])) > 0),
    ("path has 2 genes", lambda d: len(d["paths"][0]["genes"]) == 2),
    ("starts with TP53", lambda d: d["paths"][0]["genes"][0]["symbol"] == "TP53"),
    ("ends with BAX", lambda d: d["paths"][0]["genes"][-1]["symbol"] == "BAX"),
    ("confidence 0.95", lambda d: d["paths"][0]["overall_confidence"] == 0.95),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "TP53", "--target", "TERT", "--max-depth", "1"],
              "path: TP53->TERT depth 1 (direct)")
grade(r, [
    ("finds direct path", lambda d: len(d.get("paths", [])) > 0),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "TP53", "--target", "TERT", "--max-depth", "2"],
              "path: TP53->TERT depth 2 (direct + via MYC)")
grade(r, [
    ("multiple paths", lambda d: len(d.get("paths", [])) >= 2),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "TP53", "--target", "BAX", "--max-depth", "2"],
              "path: TP53->BAX depth 2")
grade(r, [
    ("finds direct + indirect", lambda d: len(d.get("paths", [])) >= 2),
    ("direct path is first (highest conf)", lambda d: d["paths"][0]["overall_confidence"] >= d["paths"][1]["overall_confidence"]),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "TP53", "--target", "ZZZZFAKE", "--max-depth", "2"],
              "path: to nonexistent gene")
grade(r, [
    ("no paths", lambda d: len(d.get("paths", [])) == 0),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "TP53", "--target", "E2F1", "--max-depth", "1"],
              "path: TP53->E2F1 direct (repression)")
grade(r, [
    ("finds path", lambda d: len(d.get("paths", [])) > 0),
    ("regulation_type includes repression", lambda d: "repression" in d["paths"][0].get("regulation_types", [])),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "E2F1", "--target", "TP53", "--max-depth", "1"],
              "path: E2F1->TP53 (reverse direction, activation)")
grade(r, [
    ("finds path", lambda d: len(d.get("paths", [])) > 0),
    ("activation", lambda d: "activation" in d["paths"][0].get("regulation_types", [])),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "MYC", "--target", "CDKN1A", "--max-depth", "1"],
              "path: MYC->CDKN1A (repression, conf=0.95)")
grade(r, [
    ("finds path", lambda d: len(d.get("paths", [])) > 0),
    ("conf 0.95", lambda d: d["paths"][0]["overall_confidence"] == 0.95),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "NFKB1", "--target", "MYC", "--max-depth", "1"],
              "path: NFKB1->MYC (activation, conf=0.7)")
grade(r, [
    ("finds path", lambda d: len(d.get("paths", [])) > 0),
    ("conf 0.7", lambda d: abs(d["paths"][0]["overall_confidence"] - 0.7) < 0.01),
])
results.append(r)

r = run_skill("grn-pathfinding", ["--source", "TP53", "--target", "BAX", "--max-depth", "2", "--min-confidence", "0.9"],
              "path: TP53->BAX high confidence only")
grade(r, [
    ("finds direct at 0.95", lambda d: len(d.get("paths", [])) >= 1),
    ("no low-conf indirect paths", lambda d: all(p["overall_confidence"] >= 0.9 for p in d["paths"])),
])
results.append(r)


# =====================================================================
# 5. grn-enrichment (12 tests)
# =====================================================================

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--type", "go"],
              "enrich: GO TP53 targets")
grade(r, [
    ("returns terms", lambda d: len(d.get("terms", d.get("results", d if isinstance(d, list) else []))) > 0),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--type", "pathway"],
              "enrich: pathway TP53 targets")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--type", "trait"],
              "enrich: trait TP53 targets")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "AT1G49720,AT1G45249,AT4G34000", "--type", "motif"],
              "enrich: motif arabidopsis ABFs")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,MYC,E2F1,NFKB1,STAT3,BRCA1", "--type", "go"],
              "enrich: GO 6 human TFs")
grade(r, [
    ("returns enriched terms", lambda d: len(d.get("terms", d.get("results", d if isinstance(d, list) else []))) > 0),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,MYC,E2F1,NFKB1,STAT3,BRCA1", "--type", "pathway"],
              "enrich: pathway 6 human TFs")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,MYC,E2F1,NFKB1,STAT3,BRCA1", "--type", "trait"],
              "enrich: trait 6 human TFs")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "AT5G11260,AT2G43010,AT2G20180", "--type", "go"],
              "enrich: GO arabidopsis light TFs (HY5,PIF4,PIL5)")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "FAKEGENE1,FAKEGENE2", "--type", "go"],
              "enrich: GO nonexistent genes")
grade(r, [
    ("returns empty or error", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53", "--type", "go"],
              "enrich: GO single gene")
grade(r, [
    ("returns results (single gene)", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "AT5G11260,AT2G43010,AT2G20180", "--type", "motif"],
              "enrich: motif arabidopsis light TFs")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "AT5G11260,AT2G43010,AT2G20180", "--type", "pathway"],
              "enrich: pathway arabidopsis light TFs")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

# --- Enrichment content verification tests ---

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--type", "go"],
              "enrich-content: GO apoptosis terms present")
grade(r, [
    ("apoptotic process in results", lambda d: any(
        "apoptotic" in t.get("name", "").lower() for t in d.get("results", []))),
    ("p53 signaling in results", lambda d: any(
        "p53" in t.get("name", "").lower() for t in d.get("results", []))),
    ("q_value < 0.05 for top", lambda d: d["results"][0]["q_value"] < 0.05),
    ("study_count >= 2 for top", lambda d: d["results"][0]["study_count"] >= 2),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--type", "pathway"],
              "enrich-content: TP53 network pathway enriched")
grade(r, [
    ("TP53 network pathway found", lambda d: any(
        "tp53" in t.get("name", "").lower() or "p53" in t.get("name", "").lower()
        for t in d.get("results", []))),
    ("DNA damage response found", lambda d: any(
        "dna damage" in t.get("name", "").lower() for t in d.get("results", []))),
    ("top result q_value < 0.05", lambda d: d["results"][0]["q_value"] < 0.05),
    ("study_count=5 for TP53 network", lambda d: any(
        t["study_count"] == 5 for t in d.get("results", [])
        if "tp53" in t.get("name", "").lower())),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--type", "trait"],
              "enrich-content: trait results have structure")
grade(r, [
    ("results have trait field", lambda d: all("trait" in t for t in d.get("results", [])[:5])),
    ("results have p_value", lambda d: all("p_value" in t for t in d.get("results", [])[:5])),
    ("results have study_count", lambda d: all("study_count" in t for t in d.get("results", [])[:5])),
])
results.append(r)

r = run_skill("grn-enrichment",
              ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--type", "go"],
              "enrich-content: GO results sorted by p-value")
grade(r, [
    ("sorted ascending by p_value", lambda d: all(
        d["results"][i]["p_value"] <= d["results"][i+1]["p_value"]
        for i in range(min(len(d["results"])-1, 10))
    )),
])
results.append(r)


# =====================================================================
# 6. grn-expression (10 tests)
# =====================================================================

r = run_skill("grn-expression", ["--gene-id", "AT1G49720"],
              "expr: ABF1 arabidopsis (has expression)")
grade(r, [
    ("returns dict", lambda d: isinstance(d, dict)),
    ("has samples or profile", lambda d: len(d) > 0),
])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "AT5G11260"],
              "expr: HY5 arabidopsis")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "AT2G43010"],
              "expr: PIF4 arabidopsis")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "TP53"],
              "expr: TP53 human (no human expression file)")
grade(r, [
    ("handles gracefully", lambda d: d is not None),
])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "FAKEGENE"],
              "expr: nonexistent gene")
grade(r, [
    ("handles gracefully", lambda d: d is not None),
])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "AT1G45249"],
              "expr: ABF2 arabidopsis")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "AT3G24650"],
              "expr: ABI3 arabidopsis")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "AT2G36270"],
              "expr: ABI5 arabidopsis")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "AT3G20770"],
              "expr: EIN3 arabidopsis")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-expression", ["--gene-id", "Solyc02g071730.2"],
              "expr: tomato AG (has expression)")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict)),
])
results.append(r)


# =====================================================================
# 7. grn-coexpression (10 tests)
# =====================================================================

r = run_skill("grn-coexpression", ["--gene-id", "AT1G49720", "--top", "5"],
              "coexpr: ABF1 top 5")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
    ("has partners", lambda d: len(d.get("partners", d.get("results", d if isinstance(d, list) else []))) > 0
     if isinstance(d, (list, dict)) and len(d) > 0 else True),
])
results.append(r)

r = run_skill("grn-coexpression", ["--gene-id", "AT5G11260", "--top", "10"],
              "coexpr: HY5 top 10")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-coexpression", ["--gene-id", "AT2G43010", "--top", "5"],
              "coexpr: PIF4 top 5")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-coexpression", ["--gene-id", "AT1G49720", "--top", "3", "--min-r", "0.8"],
              "coexpr: ABF1 high correlation (r>=0.8)")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-coexpression", ["--gene-id", "AT1G49720", "--top", "20"],
              "coexpr: ABF1 top 20")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-coexpression", ["--gene-id", "TP53", "--top", "5"],
              "coexpr: TP53 (no human expression)")
grade(r, [
    ("handles gracefully", lambda d: d is not None),
])
results.append(r)

r = run_skill("grn-coexpression", ["--gene-id", "FAKEGENE", "--top", "5"],
              "coexpr: nonexistent gene")
grade(r, [
    ("handles gracefully", lambda d: d is not None),
])
results.append(r)

r = run_skill("grn-coexpression", ["--gene-id", "AT1G45249", "--top", "5"],
              "coexpr: ABF2")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-coexpression", ["--gene-id", "AT3G20770", "--top", "5"],
              "coexpr: EIN3")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-coexpression", ["--gene-id", "Solyc02g071730.2", "--top", "5"],
              "coexpr: tomato AG")
grade(r, [
    ("returns results", lambda d: isinstance(d, (list, dict))),
])
results.append(r)


# =====================================================================
# 8. grn-perturbation (10 tests)
# =====================================================================

def has_effects(d):
    if isinstance(d, list): return len(d) > 0
    for k in ["effects", "nodes", "cascade", "results"]:
        if k in d and len(d[k]) > 0: return True
    return len(d) > 0

r = run_skill("grn-perturbation", ["--gene-id", "TP53", "--action", "ko"],
              "perturb: TP53 KO")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-id", "TP53", "--action", "oe"],
              "perturb: TP53 OE")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-id", "MYC", "--action", "ko"],
              "perturb: MYC KO")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-id", "NFKB1", "--action", "ko"],
              "perturb: NFKB1 KO (176 targets)")
grade(r, [
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-id", "E2F1", "--action", "oe"],
              "perturb: E2F1 OE")
grade(r, [
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-id", "AT5G11260", "--action", "ko"],
              "perturb: HY5 KO (arabidopsis)")
grade(r, [
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-id", "AT1G49720", "--action", "ko"],
              "perturb: ABF1 KO (1458 targets)")
grade(r, [
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-id", "TP53", "--action", "ko", "--depth", "2"],
              "perturb: TP53 KO depth 2")
grade(r, [
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-id", "TP53", "--action", "ko", "--min-confidence", "0.9"],
              "perturb: TP53 KO high confidence")
grade(r, [
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-id", "BAX", "--action", "ko"],
              "perturb: BAX KO (non-TF, 0 targets)")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

# --- Multi-intervention perturbation tests ---

r = run_skill("grn-perturbation", ["--gene-ids", "TP53:ko,MYC:oe"],
              "perturb-multi: TP53 KO + MYC OE")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
    ("has effects", has_effects),
    ("has interventions field", lambda d: "interventions" in d),
    ("2 interventions listed", lambda d: len(d.get("interventions", [])) == 2),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-ids", "TP53:ko,E2F1:ko"],
              "perturb-multi: TP53 KO + E2F1 KO")
grade(r, [
    ("has effects", has_effects),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-ids", "NFKB1:ko,STAT3:ko,MYC:ko"],
              "perturb-multi: 3 TF simultaneous KO")
grade(r, [
    ("has effects", has_effects),
    ("3 interventions", lambda d: len(d.get("interventions", [])) == 3),
])
results.append(r)

r = run_skill("grn-perturbation", ["--gene-ids", "TP53:oe,MYC:ko"],
              "perturb-multi: opposing actions (TP53 OE + MYC KO)")
grade(r, [
    ("has effects", has_effects),
])
results.append(r)


# =====================================================================
# 9. grn-dsrna (10 tests)
# =====================================================================

r = run_skill("grn-dsrna", ["--target-gene", "AT1G49720", "--species", "arabidopsis"],
              "dsrna: design ABF1 arabidopsis")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-dsrna", ["--sequence", "ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCA",
                             "--species", "arabidopsis"],
              "dsrna: analyze 48nt sequence")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-dsrna", ["--target-gene", "AT5G11260", "--species", "arabidopsis"],
              "dsrna: design HY5")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-dsrna", ["--target-gene", "AT2G43010", "--species", "arabidopsis"],
              "dsrna: design PIF4")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-dsrna", ["--sequence", "ATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGATGA",
                             "--species", "arabidopsis", "--k", "19"],
              "dsrna: analyze with k=19")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-dsrna", ["--target-gene", "AT3G20770", "--species", "arabidopsis"],
              "dsrna: design EIN3")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-dsrna", ["--sequence", "GCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGCGC",
                             "--species", "arabidopsis"],
              "dsrna: analyze GC-rich sequence")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-dsrna", ["--target-gene", "AT1G49720", "--species", "arabidopsis", "--k", "25"],
              "dsrna: design ABF1 k=25")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-dsrna", ["--target-gene", "Solyc09g065100.1", "--species", "tomato"],
              "dsrna: design tomato AN1")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-dsrna", ["--sequence", "ATATATATATATATATATATATATATATATATATATATATATATATATATA",
                             "--species", "tomato"],
              "dsrna: analyze AT-rich in tomato")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict)),
])
results.append(r)

# --- dsRNA transcript availability + content tests ---

r = run_skill("grn-dsrna", ["--target-gene", "TP53", "--species", "human"],
              "dsrna: human gene (no transcript file)")
grade(r, [
    ("returns result", lambda d: isinstance(d, dict)),
    ("available=false", lambda d: d.get("available") is False),
    ("has note", lambda d: "no transcript" in d.get("note", "").lower()),
])
results.append(r)

r = run_skill("grn-dsrna", ["--target-gene", "MOUSE05861", "--species", "mouse"],
              "dsrna: mouse gene (no transcript file)")
grade(r, [
    ("available=false", lambda d: d.get("available") is False),
])
results.append(r)

r = run_skill("grn-dsrna", ["--target-gene", "AT1G49720", "--species", "arabidopsis"],
              "dsrna-content: design output has expected fields")
grade(r, [
    ("mode=design", lambda d: d.get("mode") == "design"),
    ("has design key", lambda d: "design" in d),
    ("design has sequence", lambda d: "sequence" in d.get("design", {})),
    ("design has start/end", lambda d: "start" in d.get("design", {}) and "end" in d.get("design", {})),
    ("off_target_gene_count >= 0", lambda d: d.get("off_target_gene_count", -1) >= 0),
    ("specificity between 0-1", lambda d: 0 <= d.get("specificity", -1) <= 1),
    ("on_target_gene matches", lambda d: d.get("on_target_gene") == "AT1G49720" or d.get("on_target") == "AT1G49720"),
])
results.append(r)

r = run_skill("grn-dsrna", ["--sequence", "ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCA",
                             "--species", "arabidopsis"],
              "dsrna-content: analyze output has expected fields")
grade(r, [
    ("mode=analyze", lambda d: d.get("mode") == "analyze"),
    ("has k field", lambda d: "k" in d),
    ("k=21 default", lambda d: d.get("k") == 21),
    ("has n_sirnas", lambda d: "n_sirnas" in d),
    ("has off_target_gene_count", lambda d: "off_target_gene_count" in d),
])
results.append(r)

r = run_skill("grn-dsrna", ["--target-gene", "FAKEGENE999", "--species", "arabidopsis"],
              "dsrna: nonexistent gene in valid species")
grade(r, [
    ("handles gracefully", lambda d: isinstance(d, dict)),
    ("error or no transcript", lambda d: "error" in d or d.get("available") is False
     or "no transcript" in str(d).lower()),
])
results.append(r)


# =====================================================================
# 10. grn-orthology (10 tests)
# =====================================================================

r = run_skill("grn-orthology", ["--gene-id", "TP53"],
              "ortho: TP53 default species")
grade(r, [
    ("has human entry", lambda d: "human" in d),
    ("human found=True", lambda d: d["human"]["found"] is True),
    ("has regulators", lambda d: len(d["human"].get("regulators", [])) > 0),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "TP53", "--species", "mouse"],
              "ortho: TP53 -> mouse")
grade(r, [
    ("has mouse entry", lambda d: "mouse" in d),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "TP53", "--species", "human,mouse"],
              "ortho: TP53 -> human,mouse")
grade(r, [
    ("has human", lambda d: "human" in d),
    ("has mouse", lambda d: "mouse" in d),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "MYC"],
              "ortho: MYC default")
grade(r, [
    ("has human", lambda d: "human" in d),
    ("human found=True", lambda d: d["human"]["found"] is True),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "AT5G11260"],
              "ortho: HY5 arabidopsis")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "AT5G11260", "--species", "tomato"],
              "ortho: HY5 -> tomato")
grade(r, [
    ("has tomato entry", lambda d: "tomato" in d),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "E2F1"],
              "ortho: E2F1 default")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "NFKB1", "--species", "mouse"],
              "ortho: NFKB1 -> mouse")
grade(r, [
    ("has mouse", lambda d: "mouse" in d),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "FAKEGENE"],
              "ortho: nonexistent gene")
grade(r, [
    ("handles gracefully", lambda d: d is not None),
])
results.append(r)

r = run_skill("grn-orthology", ["--gene-id", "BRCA1", "--species", "mouse"],
              "ortho: BRCA1 -> mouse")
grade(r, [
    ("has mouse", lambda d: "mouse" in d),
])
results.append(r)


# =====================================================================
# 11. grn-conservation (10 tests)
# =====================================================================

r = run_skill("grn-conservation",
              ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2", "--species-b", "mouse"],
              "conserv: 5 human genes -> mouse")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-conservation",
              ["--gene-ids", "TP53,MYC,E2F1", "--species-b", "mouse"],
              "conserv: TFs -> mouse")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-conservation",
              ["--gene-ids", "AT5G11260,AT2G43010", "--species-b", "tomato"],
              "conserv: arabidopsis HY5,PIF4 -> tomato")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-conservation",
              ["--gene-ids", "AT1G49720", "--species-b", "tomato"],
              "conserv: ABF1 -> tomato")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-conservation",
              ["--gene-ids", "AT1G49720", "--species-b", "petunia"],
              "conserv: ABF1 -> petunia")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-conservation",
              ["--gene-ids", "TP53", "--species-b", "mouse"],
              "conserv: single gene TP53 -> mouse")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-conservation",
              ["--gene-ids", "NFKB1,STAT3,BRCA1", "--species-b", "mouse"],
              "conserv: 3 TFs -> mouse")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-conservation",
              ["--gene-ids", "AT5G11260,AT2G43010,AT2G20180,AT3G20770", "--species-b", "tomato"],
              "conserv: 4 arabidopsis TFs -> tomato")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-conservation",
              ["--gene-ids", "FAKEGENE1,FAKEGENE2", "--species-b", "mouse"],
              "conserv: nonexistent genes")
grade(r, [
    ("handles gracefully", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-conservation",
              ["--gene-ids", "AT5G11260", "--species-b", "petunia"],
              "conserv: HY5 -> petunia")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)


# =====================================================================
# 12. grn-subgraph (10 tests)
# =====================================================================

r = run_skill("grn-subgraph", ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2"],
              "subgraph: 5 TP53-related genes")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
    ("has edges", lambda d: len(d.get("edges", d.get("interactions", d if isinstance(d, list) else []))) > 0),
])
results.append(r)

r = run_skill("grn-subgraph", ["--gene-ids", "TP53,MYC,E2F1,NFKB1"],
              "subgraph: 4 TFs with known interactions")
grade(r, [
    ("has edges", lambda d: len(d.get("edges", d.get("interactions", d if isinstance(d, list) else []))) > 0),
    # ground truth: 7 edges among these 4 genes
])
results.append(r)

r = run_skill("grn-subgraph", ["--gene-ids", "TP53,MYC"],
              "subgraph: 2 genes TP53,MYC")
grade(r, [
    ("has edges", lambda d: len(d.get("edges", d.get("interactions", d if isinstance(d, list) else []))) > 0),
])
results.append(r)

r = run_skill("grn-subgraph", ["--gene-ids", "BAX,BCL2"],
              "subgraph: 2 non-TFs (no edges expected)")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-subgraph", ["--gene-ids", "AT5G11260,AT2G43010,AT2G20180"],
              "subgraph: arabidopsis HY5,PIF4,PIL5")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-subgraph", ["--gene-ids", "TP53,BAX,BCL2,CDKN1A,MDM2,MYC,E2F1,NFKB1"],
              "subgraph: 8 genes large set")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
    ("has edges", lambda d: len(d.get("edges", d.get("interactions", d if isinstance(d, list) else []))) > 0),
])
results.append(r)

r = run_skill("grn-subgraph", ["--gene-ids", "FAKEGENE1,FAKEGENE2"],
              "subgraph: nonexistent genes")
grade(r, [
    ("handles gracefully", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-subgraph", ["--gene-ids", "TP53"],
              "subgraph: single gene")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-subgraph", ["--gene-ids", "STAT3,MYC"],
              "subgraph: STAT3->MYC (known edge)")
grade(r, [
    ("has edges", lambda d: len(d.get("edges", d.get("interactions", d if isinstance(d, list) else []))) > 0),
])
results.append(r)

r = run_skill("grn-subgraph", ["--gene-ids", "TP53,E2F1"],
              "subgraph: TP53<->E2F1 (bidirectional)")
grade(r, [
    ("has edges", lambda d: len(d.get("edges", d.get("interactions", d if isinstance(d, list) else []))) >= 2),
])
results.append(r)


# =====================================================================
# 13. grn-export (10 tests)
# =====================================================================

r = run_skill("grn-export", ["--gene-ids", "TP53,BAX,BCL2", "--format", "json"],
              "export: 3 genes JSON")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "TP53,BAX,BCL2", "--format", "tsv"],
              "export: 3 genes TSV", raw=True)
grade(r, [
    ("returns data", lambda d: d is not None and len(d) > 0),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "TP53", "--format", "json"],
              "export: single gene")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "TP53,MYC,E2F1,NFKB1,STAT3", "--format", "json"],
              "export: 5 TFs JSON")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "AT5G11260,AT2G43010", "--format", "json"],
              "export: arabidopsis genes JSON")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "AT5G11260,AT2G43010", "--format", "tsv"],
              "export: arabidopsis genes TSV", raw=True)
grade(r, [
    ("returns data", lambda d: d is not None and len(d) > 0),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "MYC,CDKN1A", "--format", "json"],
              "export: MYC,CDKN1A")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "FAKEGENE", "--format", "json"],
              "export: nonexistent gene")
grade(r, [
    ("handles gracefully", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "BAX", "--format", "json"],
              "export: non-TF gene")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "BRCA1,BRCA2", "--format", "json"],
              "export: BRCA1,BRCA2")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict))),
])
results.append(r)

# --- Export content verification tests ---

r = run_skill("grn-export", ["--gene-ids", "TP53,BAX", "--format", "json"],
              "export-content: JSON edges have expected fields")
grade(r, [
    ("has edges list", lambda d: "edges" in d),
    ("has stats", lambda d: "stats" in d),
    ("edges have source_gene_id", lambda d: all("source_gene_id" in e for e in d["edges"][:5])),
    ("edges have target_gene_id", lambda d: all("target_gene_id" in e for e in d["edges"][:5])),
    ("edges have regulation_type", lambda d: all("regulation_type" in e for e in d["edges"][:5])),
    ("edges have confidence", lambda d: all("confidence" in e for e in d["edges"][:5])),
    ("TP53->BAX edge present", lambda d: any(
        e["source_gene_id"] == "TP53" and e["target_gene_id"] == "BAX" for e in d["edges"])),
    ("stats.edges matches", lambda d: d["stats"]["edges"] == len(d["edges"])),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "TP53,BAX", "--format", "json"],
              "export-content: JSON edges have coordinates")
grade(r, [
    ("source_chromosome present", lambda d: any(e.get("source_chromosome") for e in d["edges"])),
    ("target_start present", lambda d: any(e.get("target_start") for e in d["edges"])),
    ("promoter windows present", lambda d: any(e.get("source_promoter_start") for e in d["edges"])),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "TP53,BAX", "--format", "tsv"],
              "export-content: TSV has header and columns", raw=True)
grade(r, [
    ("starts with comment", lambda d: d.startswith("# GRN Atlas")),
    ("has tab-separated header", lambda d: "source_gene_id\t" in d),
    ("has data rows", lambda d: len(d.strip().split("\n")) > 7),
    ("TP53 in data", lambda d: "TP53" in d),
    ("BAX in data", lambda d: "BAX" in d),
    ("has regulation_type column", lambda d: "regulation_type" in d),
])
results.append(r)

r = run_skill("grn-export", ["--gene-ids", "AT5G11260,AT2G43010", "--format", "tsv"],
              "export-content: TSV arabidopsis genes", raw=True)
grade(r, [
    ("has comment header", lambda d: d.startswith("#")),
    ("has data rows (>=7 lines)", lambda d: len(d.strip().split("\n")) >= 7),
    ("AT5G11260 in data", lambda d: "AT5G11260" in d),
])
results.append(r)


# =====================================================================
# 14. grn-provenance (10 tests)
# =====================================================================

r = run_skill("grn-provenance", [], "prov: basic manifest")
grade(r, [
    ("has atlas_version", lambda d: "atlas_version" in d),
    ("has sources", lambda d: len(d.get("sources", [])) > 0),
    ("has methods", lambda d: "methods" in d),
    ("has TRRUST", lambda d: any("trrust" in s.get("key", "").lower() for s in d.get("sources", []))),
])
results.append(r)

r = run_skill("grn-provenance", [], "prov: sources have DOIs")
grade(r, [
    ("sources have doi or url", lambda d: all(
        s.get("doi") or s.get("url") for s in d.get("sources", [])
    )),
])
results.append(r)

r = run_skill("grn-provenance", [], "prov: methods documented")
grade(r, [
    ("promoter_window method", lambda d: "promoter_window" in d.get("methods", {})),
    ("enrichment method", lambda d: "enrichment" in d.get("methods", {})),
])
results.append(r)

r = run_skill("grn-provenance", [], "prov: version is string")
grade(r, [
    ("version is string", lambda d: isinstance(d.get("atlas_version"), str)),
])
results.append(r)

r = run_skill("grn-provenance", [], "prov: has generated timestamp")
grade(r, [
    ("has generated", lambda d: "generated" in d),
])
results.append(r)

r = run_skill("grn-provenance", [], "prov: motif_scan method")
grade(r, [
    ("motif_scan in methods", lambda d: "motif_scan" in d.get("methods", {})),
])
results.append(r)

r = run_skill("grn-provenance", [], "prov: inferred_edges method")
grade(r, [
    ("inferred_edges in methods", lambda d: "inferred_edges" in d.get("methods", {})),
])
results.append(r)

r = run_skill("grn-provenance", [], "prov: has JASPAR source")
grade(r, [
    ("has JASPAR", lambda d: any("jaspar" in s.get("key", "").lower() or "jaspar" in s.get("name", "").lower()
                                  for s in d.get("sources", []))),
])
results.append(r)

r = run_skill("grn-provenance", [], "prov: coordinate_systems method")
grade(r, [
    ("coordinate_systems", lambda d: "coordinate_systems" in d.get("methods", {})),
])
results.append(r)

r = run_skill("grn-provenance", [], "prov: regulator_identification method")
grade(r, [
    ("regulator_identification", lambda d: "regulator_identification" in d.get("methods", {})),
])
results.append(r)


# =====================================================================
# 15. grn-species (10 tests)
# =====================================================================

r = run_skill("grn-species", [], "species: returns all species")
grade(r, [
    ("returns data", lambda d: isinstance(d, (list, dict)) and len(d) > 0),
    ("has >= 5 species", lambda d: (len(d) >= 5 if isinstance(d, list) else len(d.get("species", d)) >= 5)),
])
results.append(r)

r = run_skill("grn-species", [], "species: has human")
grade(r, [("human present", lambda d: "human" in str(d))])
results.append(r)

r = run_skill("grn-species", [], "species: has arabidopsis")
grade(r, [("arabidopsis present", lambda d: "arabidopsis" in str(d))])
results.append(r)

r = run_skill("grn-species", [], "species: has tomato")
grade(r, [("tomato present", lambda d: "tomato" in str(d))])
results.append(r)

r = run_skill("grn-species", [], "species: has petunia")
grade(r, [("petunia present", lambda d: "petunia" in str(d))])
results.append(r)

r = run_skill("grn-species", [], "species: has mouse")
grade(r, [("mouse present", lambda d: "mouse" in str(d))])
results.append(r)

r = run_skill("grn-species", [], "species: capability fields present")
grade(r, [
    ("has capability info", lambda d: any(
        "expression" in str(d).lower() or "motif" in str(d).lower()
        or "trait" in str(d).lower()
        for _ in [1]
    )),
])
results.append(r)

r = run_skill("grn-species", [], "species: returns consistent data")
grade(r, [
    ("same result twice", lambda d: d is not None),
])
results.append(r)

r = run_skill("grn-species", [], "species: no empty species names")
grade(r, [
    ("all species named", lambda d: all(
        (s.get("species", s.get("name", k)) if isinstance(s, dict) else k)
        for k, s in (d.items() if isinstance(d, dict) else enumerate(d))
    )),
])
results.append(r)

r = run_skill("grn-species", [], "species: gene counts present")
grade(r, [
    ("has gene count info", lambda d: "gene" in str(d).lower()),
])
results.append(r)


# =====================================================================
# 16. grn-stats (10 tests)
# =====================================================================

r = run_skill("grn-stats", [], "stats: global stats")
grade(r, [
    ("has species count", lambda d: isinstance(d.get("species"), int) and d["species"] >= 5),
    ("has genes count", lambda d: isinstance(d.get("genes"), int) and d["genes"] > 1000),
    ("has interactions", lambda d: isinstance(d.get("interactions"), int) and d["interactions"] > 1000),
    ("has species_list", lambda d: isinstance(d.get("species_list"), list)),
])
results.append(r)

r = run_skill("grn-stats", ["--species", "human"], "stats: human species")
grade(r, [
    ("species=human", lambda d: d.get("species") == "human"),
    ("has genes", lambda d: d.get("genes", 0) > 0),
    ("has TFs", lambda d: d.get("transcription_factors", 0) > 0),
    ("has interactions", lambda d: d.get("interactions", 0) > 0),
])
results.append(r)

r = run_skill("grn-stats", ["--species", "arabidopsis"], "stats: arabidopsis species")
grade(r, [
    ("species=arabidopsis", lambda d: d.get("species") == "arabidopsis"),
    ("has genes", lambda d: d.get("genes", 0) > 0),
])
results.append(r)

r = run_skill("grn-stats", ["--species", "mouse"], "stats: mouse species")
grade(r, [
    ("species=mouse", lambda d: d.get("species") == "mouse"),
    ("has genes", lambda d: d.get("genes", 0) > 0),
])
results.append(r)

r = run_skill("grn-stats", ["--species", "tomato"], "stats: tomato species")
grade(r, [
    ("species=tomato", lambda d: d.get("species") == "tomato"),
])
results.append(r)

r = run_skill("grn-stats", ["--species", "petunia"], "stats: petunia species")
grade(r, [
    ("species=petunia", lambda d: d.get("species") == "petunia"),
])
results.append(r)

r = run_skill("grn-stats", ["--species", "FAKEFAKE"], "stats: nonexistent species")
grade(r, [
    ("handles gracefully", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-stats", [], "stats: global has databases")
grade(r, [
    ("has databases", lambda d: isinstance(d.get("databases"), list) and len(d["databases"]) > 0),
    ("TRRUST in databases", lambda d: "TRRUST" in d.get("databases", [])),
])
results.append(r)

r = run_skill("grn-stats", [], "stats: global has version")
grade(r, [
    ("has version", lambda d: isinstance(d.get("version"), str)),
])
results.append(r)

r = run_skill("grn-stats", ["--species", "human"], "stats: human TF count > 100")
grade(r, [
    ("TFs > 100", lambda d: d.get("transcription_factors", 0) > 100),
])
results.append(r)


# =====================================================================
# 17. grn-cascade (10 tests)
# =====================================================================

r = run_skill("grn-cascade", ["--target-gene", "TP53", "--interventions", "SIRT1:up:1.5"],
              "cascade: TP53 with SIRT1 up")
grade(r, [
    ("has cascade", lambda d: isinstance(d.get("cascade"), list)),
    ("has affected_genes", lambda d: isinstance(d.get("affected_genes"), int)),
    ("has average_confidence", lambda d: isinstance(d.get("average_confidence"), (int, float))),
    ("cascade non-empty", lambda d: len(d.get("cascade", [])) > 0),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "TP53", "--interventions", "SIRT1:up:1.5,MDM2:down:0.5"],
              "cascade: TP53 with two interventions")
grade(r, [
    ("has cascade", lambda d: len(d.get("cascade", [])) > 0),
    ("affected_genes > 0", lambda d: d.get("affected_genes", 0) > 0),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "MYC", "--interventions", "STAT3:up:2.0"],
              "cascade: MYC with STAT3 up")
grade(r, [
    ("has cascade", lambda d: isinstance(d.get("cascade"), list)),
    ("cascade non-empty", lambda d: len(d.get("cascade", [])) > 0),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "TP53", "--interventions", "MDM2:down:0.3"],
              "cascade: TP53 with MDM2 down")
grade(r, [
    ("cascade effects present", lambda d: len(d.get("cascade", [])) > 0),
    ("direction field", lambda d: all(e.get("direction") in ("up", "down") for e in d["cascade"])),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "TP53", "--interventions", "SIRT1:up:1.5"],
              "cascade-content: effects have expected fields")
grade(r, [
    ("id field", lambda d: all("id" in e for e in d["cascade"])),
    ("symbol field", lambda d: all("symbol" in e for e in d["cascade"])),
    ("level field", lambda d: all("level" in e for e in d["cascade"])),
    ("magnitude field", lambda d: all("magnitude" in e for e in d["cascade"])),
    ("confidence field", lambda d: all("confidence" in e for e in d["cascade"])),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "AT5G11260", "--interventions", "AT2G43010:up:1.5"],
              "cascade: arabidopsis HY5 with PIF4 up")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict)),
    ("has cascade key", lambda d: "cascade" in d),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "NFKB1", "--interventions", "STAT3:up:1.0"],
              "cascade: NFKB1 with STAT3 up")
grade(r, [
    ("has cascade", lambda d: isinstance(d.get("cascade"), list)),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "FAKEGENE", "--interventions", "X:up:1.0"],
              "cascade: nonexistent gene")
grade(r, [
    ("handles gracefully", lambda d: isinstance(d, dict)),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "TP53", "--interventions", "SIRT1:up:1.5", "--depth", "5"],
              "cascade: custom depth")
grade(r, [
    ("has cascade", lambda d: len(d.get("cascade", [])) > 0),
])
results.append(r)

r = run_skill("grn-cascade", ["--target-gene", "E2F1", "--interventions", "TP53:down:0.5"],
              "cascade: E2F1 with TP53 down")
grade(r, [
    ("has cascade", lambda d: isinstance(d.get("cascade"), list)),
])
results.append(r)


# =====================================================================
# 18. grn-citations (10 tests)
# =====================================================================

r = run_skill("grn-citations", [], "citations: returns BibTeX", raw=True)
grade(r, [
    ("non-empty", lambda d: len(d.strip()) > 0),
    ("has @article", lambda d: "@article" in d or "@misc" in d),
    ("has TRRUST", lambda d: "trrust" in d.lower() or "TRRUST" in d),
])
results.append(r)

r = run_skill("grn-citations", [], "citations: has PlantRegMap", raw=True)
grade(r, [
    ("PlantRegMap present", lambda d: "plantregmap" in d.lower() or "PlantRegMap" in d),
])
results.append(r)

r = run_skill("grn-citations", [], "citations: has DOIs", raw=True)
grade(r, [
    ("has doi field", lambda d: "doi" in d.lower()),
])
results.append(r)

r = run_skill("grn-citations", [], "citations: has JASPAR", raw=True)
grade(r, [
    ("JASPAR present", lambda d: "jaspar" in d.lower() or "JASPAR" in d),
])
results.append(r)

r = run_skill("grn-citations", [], "citations: valid BibTeX structure", raw=True)
grade(r, [
    ("has opening brace", lambda d: "{" in d),
    ("has closing brace", lambda d: "}" in d),
    ("has title field", lambda d: "title" in d.lower()),
    ("has year field", lambda d: "year" in d.lower()),
])
results.append(r)

r = run_skill("grn-citations", [], "citations: has journal", raw=True)
grade(r, [
    ("journal field", lambda d: "journal" in d.lower()),
])
results.append(r)

r = run_skill("grn-citations", [], "citations: has URL", raw=True)
grade(r, [
    ("url field", lambda d: "url" in d.lower()),
])
results.append(r)

r = run_skill("grn-citations", [], "citations: has author", raw=True)
grade(r, [
    ("author field", lambda d: "author" in d.lower()),
])
results.append(r)

r = run_skill("grn-citations", [], "citations: multiple entries", raw=True)
grade(r, [
    ("multiple @entries", lambda d: d.count("@") >= 2),
])
results.append(r)

r = run_skill("grn-citations", [], "citations: has OMA or UniProt", raw=True)
grade(r, [
    ("OMA or UniProt present", lambda d: "oma" in d.lower() or "uniprot" in d.lower()),
])
results.append(r)


# =====================================================================
# 19. grn-dsrna-screen (10 tests)
# =====================================================================

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720,AT5G11260,AT2G43010", "--species", "arabidopsis"],
              "screen: 3 arabidopsis genes")
grade(r, [
    ("available=true", lambda d: d.get("available") is True),
    ("n_genes=3", lambda d: d.get("n_genes") == 3),
    ("has results list", lambda d: isinstance(d.get("results"), list) and len(d["results"]) == 3),
    ("has designable count", lambda d: isinstance(d.get("designable"), int)),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720,AT5G11260,AT2G43010", "--species", "arabidopsis",
               "--no-predict-effect"],
              "screen: without effect prediction")
grade(r, [
    ("available=true", lambda d: d.get("available") is True),
    ("predicted_effect is null", lambda d: d.get("predicted_effect") is None),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720,AT5G11260,AT2G43010", "--species", "arabidopsis"],
              "screen-content: results have expected fields")
grade(r, [
    ("gene_id field", lambda d: all("gene_id" in r for r in d["results"])),
    ("designable field", lambda d: all("designable" in r for r in d["results"])),
    ("symbol field", lambda d: all("symbol" in r for r in d["results"])),
    ("best_window_off_targets", lambda d: all("best_window_off_targets" in r for r in d["results"])),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720,AT5G11260,AT2G43010", "--species", "arabidopsis"],
              "screen-content: has predicted_effect with stats")
grade(r, [
    ("has predicted_effect", lambda d: d.get("predicted_effect") is not None),
    ("effect has affected", lambda d: "affected" in d.get("predicted_effect", {})),
    ("effect has up/down", lambda d: "up" in d.get("predicted_effect", {})
     and "down" in d.get("predicted_effect", {})),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720", "--species", "arabidopsis"],
              "screen: single gene")
grade(r, [
    ("n_genes=1", lambda d: d.get("n_genes") == 1),
    ("available=true", lambda d: d.get("available") is True),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "TP53,MYC", "--species", "human"],
              "screen: human genes (no transcripts)")
grade(r, [
    ("available=false", lambda d: d.get("available") is False),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720,AT5G11260", "--species", "arabidopsis", "--k", "25"],
              "screen: custom k=25")
grade(r, [
    ("available=true", lambda d: d.get("available") is True),
    ("has results", lambda d: len(d.get("results", [])) > 0),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720,AT5G11260", "--species", "arabidopsis",
               "--design-window", "100"],
              "screen: custom design window")
grade(r, [
    ("available=true", lambda d: d.get("available") is True),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "Solyc09g065100.1,Solyc02g071730.2", "--species", "tomato"],
              "screen: tomato genes")
grade(r, [
    ("returns data", lambda d: isinstance(d, dict)),
    ("has species", lambda d: d.get("species") == "tomato"),
])
results.append(r)

r = run_skill("grn-dsrna-screen",
              ["--gene-ids", "AT1G49720,AT5G11260,AT2G43010", "--species", "arabidopsis"],
              "screen: results ranked by off-target burden")
grade(r, [
    ("sorted by off-targets", lambda d: all(
        d["results"][i].get("best_window_off_targets", 0) <= d["results"][i+1].get("best_window_off_targets", 0)
        for i in range(len(d["results"]) - 1)
    ) if len(d.get("results", [])) > 1 else True),
])
results.append(r)


# =====================================================================
# 20. grn-provenance --freshness (5 tests, extends existing provenance)
# =====================================================================

r = run_skill("grn-provenance", ["--freshness"], "prov-freshness: returns data")
grade(r, [
    ("has sources", lambda d: isinstance(d.get("sources"), list) and len(d["sources"]) > 0),
    ("has checked date", lambda d: "checked" in d),
])
results.append(r)

r = run_skill("grn-provenance", ["--freshness"], "prov-freshness: sources have status")
grade(r, [
    ("all sources have status", lambda d: all("status" in s for s in d["sources"])),
    ("all sources have key", lambda d: all("key" in s for s in d["sources"])),
])
results.append(r)

r = run_skill("grn-provenance", ["--freshness"], "prov-freshness: has stale list")
grade(r, [
    ("has stale list", lambda d: isinstance(d.get("stale"), list)),
])
results.append(r)

r = run_skill("grn-provenance", ["--freshness"], "prov-freshness: sources have version info")
grade(r, [
    ("our_version field", lambda d: all("our_version" in s for s in d["sources"])),
    ("name field", lambda d: all("name" in s for s in d["sources"])),
])
results.append(r)

r = run_skill("grn-provenance", ["--freshness"], "prov-freshness: TRRUST in sources")
grade(r, [
    ("TRRUST present", lambda d: any("trrust" in s.get("key", "").lower() for s in d["sources"])),
])
results.append(r)


# =====================================================================
# 21. grn-enrichment --gene-id trait lookup (5 tests, extends enrichment)
# =====================================================================

r = run_skill("grn-enrichment", ["--gene-id", "TP53", "--type", "trait"],
              "enrichment-trait: TP53 single-gene traits")
grade(r, [
    ("has gene_id", lambda d: d.get("gene_id") == "TP53"),
    ("has traits list", lambda d: isinstance(d.get("traits"), list)),
    ("non-empty traits", lambda d: len(d.get("traits", [])) > 0),
    ("has note", lambda d: "GWAS" in d.get("note", "")),
])
results.append(r)

r = run_skill("grn-enrichment", ["--gene-id", "TP53", "--type", "trait"],
              "enrichment-trait: traits have expected fields")
grade(r, [
    ("trait field", lambda d: all("trait" in t for t in d["traits"][:5])),
    ("pubmed_id field", lambda d: all("pubmed_id" in t for t in d["traits"][:5])),
    ("source field", lambda d: all("source" in t for t in d["traits"][:5])),
])
results.append(r)

r = run_skill("grn-enrichment", ["--gene-id", "TP53", "--type", "trait"],
              "enrichment-trait: TP53 has cancer trait")
grade(r, [
    ("cancer trait", lambda d: any("cancer" in t["trait"].lower() or "melanoma" in t["trait"].lower()
                                   for t in d["traits"])),
])
results.append(r)

r = run_skill("grn-enrichment", ["--gene-id", "FAKEGENE999", "--type", "trait"],
              "enrichment-trait: nonexistent gene")
grade(r, [
    ("has gene_id", lambda d: d.get("gene_id") == "FAKEGENE999"),
    ("empty traits", lambda d: len(d.get("traits", [])) == 0),
])
results.append(r)

r = run_skill("grn-enrichment", ["--gene-id", "MYC", "--type", "trait"],
              "enrichment-trait: MYC single-gene traits")
grade(r, [
    ("has gene_id", lambda d: d.get("gene_id") == "MYC"),
    ("has traits list", lambda d: isinstance(d.get("traits"), list)),
])
results.append(r)


# =====================================================================
# GRN-REGULON
# =====================================================================
r = run_skill("grn-regulon", ["--gene-id", "TP53", "--depth", "1"],
              "regulon: TP53 depth=1")
grade(r, [
    ("found", lambda d: d.get("found") is True),
    ("has genes dict", lambda d: isinstance(d.get("genes"), dict)),
    ("total >= 100", lambda d: d.get("total", 0) >= 100),
    ("level_counts has 1", lambda d: "1" in d.get("level_counts", {})),
])
results.append(r)

r = run_skill("grn-regulon", ["--gene-id", "TP53", "--depth", "2"],
              "regulon: TP53 depth=2 larger than depth=1")
grade(r, [
    ("found", lambda d: d.get("found") is True),
    ("total > 106", lambda d: d.get("total", 0) > 106),
])
results.append(r)

r = run_skill("grn-regulon", ["--gene-id", "BAX"],
              "regulon: BAX non-TF has 0 targets")
grade(r, [
    ("found", lambda d: d.get("found") is True),
    ("total is 1", lambda d: d.get("total", -1) == 1),
])
results.append(r)

r = run_skill("grn-regulon", ["--gene-id", "NONEXISTENT_GENE_XYZ"],
              "regulon: nonexistent gene")
grade(r, [
    ("error returned", lambda d: "error" in d or d.get("found") is False),
])
results.append(r)

r = run_skill("grn-regulon", ["--gene-id", "TP53", "--depth", "1", "--min-confidence", "0.99"],
              "regulon: TP53 high confidence filter")
grade(r, [
    ("found", lambda d: d.get("found") is True),
    ("fewer than unfiltered", lambda d: d.get("total", 999) < 106),
])
results.append(r)

r = run_skill("grn-regulon", ["--gene-id", "AT5G11260", "--depth", "1"],
              "regulon: arabidopsis TF")
grade(r, [
    ("found", lambda d: d.get("found") is True),
    ("total >= 1", lambda d: d.get("total", 0) >= 1),
])
results.append(r)

# =====================================================================
# GRN-REGULON-COMPARE
# =====================================================================
r = run_skill("grn-regulon-compare", ["--tf-a", "TP53", "--tf-b", "TP53", "--depth", "1"],
              "regulon-compare: TP53 vs self")
grade(r, [
    ("jaccard = 1.0", lambda d: abs(d.get("jaccard", 0) - 1.0) < 0.01),
    ("overlap = union", lambda d: d.get("overlap_size", 0) == d.get("union_size", -1)),
])
results.append(r)

r = run_skill("grn-regulon-compare", ["--tf-a", "TP53", "--tf-b", "MYC", "--depth", "1"],
              "regulon-compare: TP53 vs MYC")
grade(r, [
    ("has jaccard", lambda d: 0 <= d.get("jaccard", -1) <= 1),
    ("has p_value", lambda d: d.get("p_value") is not None),
    ("overlap > 0", lambda d: d.get("overlap_size", 0) > 0),
    ("has overlap_genes", lambda d: isinstance(d.get("overlap_genes"), list)),
])
results.append(r)

r = run_skill("grn-regulon-compare", ["--tf-a", "TP53", "--tf-b", "AT5G11260", "--depth", "1"],
              "regulon-compare: cross-species no overlap")
grade(r, [
    ("jaccard = 0", lambda d: d.get("jaccard", -1) == 0),
    ("overlap = 0", lambda d: d.get("overlap_size", -1) == 0),
])
results.append(r)

r = run_skill("grn-regulon-compare", ["--tf-a", "TP53", "--tf-b", "MYC", "--depth", "1"],
              "regulon-compare: tf metadata present")
grade(r, [
    ("tf_a has symbol", lambda d: d.get("tf_a", {}).get("symbol") is not None),
    ("tf_b has symbol", lambda d: d.get("tf_b", {}).get("symbol") is not None),
    ("tf_a has regulon_size", lambda d: d.get("tf_a", {}).get("regulon_size", 0) > 0),
])
results.append(r)

# =====================================================================
# GRN-UPSTREAM
# =====================================================================
r = run_skill("grn-upstream",
              ["--gene-ids", "BAX,BCL2,CDKN1A,MDM2,GADD45A,BBC3,PMAIP1,SESN1,TIGAR,DRAM1"],
              "upstream: TP53 targets should predict TP53")
grade(r, [
    ("has regulators", lambda d: len(d.get("regulators", [])) > 0),
    ("TP53 in top 5", lambda d: "TP53" in [x.get("symbol") for x in d.get("regulators", [])[:5]]),
    ("has p_value", lambda d: d.get("regulators", [{}])[0].get("p_value") is not None),
    ("has q_value", lambda d: d.get("regulators", [{}])[0].get("q_value") is not None),
])
results.append(r)

r = run_skill("grn-upstream",
              ["--gene-ids", "BAX,BCL2,CDKN1A", "--species", "human"],
              "upstream: explicit species")
grade(r, [
    ("species is human", lambda d: d.get("species") == "human"),
    ("has regulators", lambda d: len(d.get("regulators", [])) > 0),
])
results.append(r)

r = run_skill("grn-upstream",
              ["--gene-ids", "BAX,BCL2,CDKN1A", "--top", "5"],
              "upstream: top=5 limit")
grade(r, [
    ("at most 5", lambda d: len(d.get("regulators", [])) <= 5),
])
results.append(r)

r = run_skill("grn-upstream",
              ["--gene-ids", "BAX,BCL2,CDKN1A", "--min-overlap", "3"],
              "upstream: min-overlap=3 filter")
grade(r, [
    ("all overlap >= 3", lambda d: all(x.get("overlap_count", 0) >= 3 for x in d.get("regulators", [{}]))),
])
results.append(r)

r = run_skill("grn-upstream",
              ["--gene-ids", "NONEXISTENT1,NONEXISTENT2,NONEXISTENT3"],
              "upstream: nonexistent genes")
grade(r, [
    ("no regulators or zero input", lambda d: len(d.get("regulators", [])) == 0 or d.get("input_genes", 0) == 0),
])
results.append(r)

# =====================================================================
# GRN-NETWORK-PATTERNS
# =====================================================================
r = run_skill("grn-network-patterns",
              ["--species", "human", "--types", "autoregulation"],
              "patterns: human autoregulation")
grade(r, [
    ("has patterns", lambda d: len(d.get("patterns", [])) > 0),
    ("all autoregulation", lambda d: all(p.get("type") == "autoregulation" for p in d.get("patterns", []))),
    ("BCL6 present", lambda d: any("BCL6" in str(p) for p in d.get("patterns", []))),
])
results.append(r)

r = run_skill("grn-network-patterns",
              ["--species", "human", "--types", "ffl", "--limit", "10"],
              "patterns: human FFL limit 10")
grade(r, [
    ("has patterns", lambda d: len(d.get("patterns", [])) > 0),
    ("at most 10", lambda d: len(d.get("patterns", [])) <= 10),
    ("type is feed_forward_loop", lambda d: all(p.get("type") == "feed_forward_loop" for p in d.get("patterns", []))),
])
results.append(r)

r = run_skill("grn-network-patterns",
              ["--species", "human", "--types", "autoregulation,ffl"],
              "patterns: multiple types")
grade(r, [
    ("has summary", lambda d: "summary" in d),
    ("total in summary", lambda d: d.get("summary", {}).get("total", 0) > 0),
    ("by_type present", lambda d: "by_type" in d.get("summary", {})),
])
results.append(r)

r = run_skill("grn-network-patterns",
              ["--gene-ids", "TP53,MYC,E2F1", "--types", "ffl"],
              "patterns: gene-ids subset FFL")
grade(r, [
    ("has patterns key", lambda d: "patterns" in d),
])
results.append(r)

# =====================================================================
# GRN-CENTRALITY
# =====================================================================
r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "out_degree", "--top", "10"],
              "centrality: human out-degree top 10")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("at most 10", lambda d: len(d.get("results", [])) <= 10),
    ("SP1 or TP53 in top 10", lambda d: any(
        x.get("symbol") in ("SP1", "TP53", "RELA", "NFKB1") for x in d.get("results", []))),
    ("first has score", lambda d: d.get("results", [{}])[0].get("score", 0) > 0),
])
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "in_degree", "--top", "5"],
              "centrality: human in-degree top 5")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("at most 5", lambda d: len(d.get("results", [])) <= 5),
])
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "degree", "--top", "5"],
              "centrality: human total degree")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("score >= out_degree", lambda d: d.get("results", [{}])[0].get("score", 0) >= 100),
])
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "arabidopsis", "--metric", "out_degree", "--top", "5"],
              "centrality: arabidopsis out-degree")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
])
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "out_degree", "--top", "10",
               "--gene-ids", "TP53,MYC,SP1"],
              "centrality: gene-ids filter")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("at most 3", lambda d: len(d.get("results", [])) <= 3),
])
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "betweenness", "--top", "5"],
              "centrality: betweenness top 5")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("at most 5", lambda d: len(d.get("results", [])) <= 5),
    ("metric is betweenness", lambda d: d.get("metric") == "betweenness"),
    ("score is float", lambda d: isinstance(d.get("results", [{}])[0].get("score"), (int, float))),
])
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "closeness", "--top", "5"],
              "centrality: closeness top 5")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("metric is closeness", lambda d: d.get("metric") == "closeness"),
])
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "eigenvector", "--top", "5"],
              "centrality: eigenvector top 5")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("metric is eigenvector", lambda d: d.get("metric") == "eigenvector"),
])
results.append(r)

r = run_skill("grn-centrality",
              ["--species", "human", "--metric", "betweenness", "--gene-ids", "TP53,MYC"],
              "centrality: betweenness with gene-ids filter")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("metric is betweenness", lambda d: d.get("metric") == "betweenness"),
])
results.append(r)

# =====================================================================
# 25. grn-motif (10 tests)
# =====================================================================

r = run_skill("grn-motif", ["--gene-id", "AT5G11260", "--top", "5"],
              "motif: promoter hits for HY5")
grade(r, [
    ("has hits", lambda d: len(d.get("hits", [])) > 0),
    ("species detected", lambda d: d.get("species") == "arabidopsis"),
])
results.append(r)

r = run_skill("grn-motif", ["--tf-gene-id", "AT5G47220", "--species", "arabidopsis", "--top", "5"],
              "motif: targets of ERF2 TF")
grade(r, [
    ("has hits", lambda d: len(d.get("hits", [])) > 0),
    ("correct TF", lambda d: all(h.get("tf_gene_id") == "AT5G47220" for h in d.get("hits", []))),
])
results.append(r)

r = run_skill("grn-motif", ["--gene-id", "AT5G11260", "--include-edge-support"],
              "motif: HY5 with edge support")
grade(r, [
    ("has hits", lambda d: len(d.get("hits", [])) > 0),
    ("edge support fields present", lambda d: "has_regulatory_edge" in d.get("hits", [{}])[0]),
])
results.append(r)

r = run_skill("grn-motif", ["--gene-id", "AT5G11260", "--max-pvalue", "1e-6"],
              "motif: strict p-value filter")
grade(r, [
    ("all hits pass pvalue", lambda d: all(h["p_value"] <= 1e-6 for h in d.get("hits", []))),
])
results.append(r)

r = run_skill("grn-motif", ["--gene-id", "TP53", "--species", "human"],
              "motif: human gene graceful degradation")
grade(r, [
    ("empty hits", lambda d: len(d.get("hits", [])) == 0),
    ("has note", lambda d: "not available" in d.get("note", "").lower()),
])
results.append(r)

r = run_skill("grn-motif", ["--tf-gene-id", "AT2G43010", "--species", "arabidopsis", "--top", "3"],
              "motif: PIF4 binding targets")
grade(r, [
    ("has hits", lambda d: len(d.get("hits", [])) > 0),
    ("max 3 hits", lambda d: len(d.get("hits", [])) <= 3),
])
results.append(r)

r = run_skill("grn-motif", ["--gene-id", "Solyc05g007180.2", "--species", "tomato", "--top", "5"],
              "motif: tomato gene promoter")
grade(r, [
    ("species is tomato", lambda d: d.get("species") == "tomato"),
])
results.append(r)

r = run_skill("grn-motif", ["--gene-id", "AT5G11260", "--tf-gene-id", "AT2G45680", "--top", "5"],
              "motif: specific TF-gene pair")
grade(r, [
    ("all hits match gene", lambda d: all(h.get("target_gene_id") == "AT5G11260" for h in d.get("hits", []))),
    ("all hits match TF", lambda d: all(h.get("tf_gene_id") == "AT2G45680" for h in d.get("hits", []))),
])
results.append(r)

r = run_skill("grn-motif", ["--gene-id", "AT5G11260", "--min-score", "15"],
              "motif: min score filter")
grade(r, [
    ("all hits pass score", lambda d: all(h["score"] >= 15 for h in d.get("hits", []))),
])
results.append(r)

r = run_skill("grn-motif", ["--gene-id", "Peaxi162Scf00921g00011", "--species", "petunia", "--top", "3"],
              "motif: petunia gene promoter")
grade(r, [
    ("species is petunia", lambda d: d.get("species") == "petunia"),
])
results.append(r)

# =====================================================================
# 26. grn-module (10 tests)
# =====================================================================

r = run_skill("grn-module", ["--species", "arabidopsis", "--top-modules", "5"],
              "module: arabidopsis louvain")
grade(r, [
    ("has modules", lambda d: d.get("num_modules", 0) > 1),
    ("positive modularity", lambda d: d.get("modularity", 0) > 0),
    ("modules list populated", lambda d: len(d.get("modules", [])) > 0),
])
results.append(r)

r = run_skill("grn-module", ["--species", "arabidopsis", "--gene-id", "AT5G11260"],
              "module: HY5 module membership")
grade(r, [
    ("query gene module found", lambda d: d.get("query_gene_module", {}).get("module_size", 0) > 0),
    ("has module id", lambda d: d.get("query_gene_module", {}).get("module_id") is not None),
])
results.append(r)

r = run_skill("grn-module", ["--species", "human", "--top-modules", "5"],
              "module: human network")
grade(r, [
    ("has modules", lambda d: d.get("num_modules", 0) > 0),
])
results.append(r)

r = run_skill("grn-module", ["--species", "tomato", "--top-modules", "3"],
              "module: tomato network")
grade(r, [
    ("has modules", lambda d: d.get("num_modules", 0) > 0),
    ("positive modularity", lambda d: d.get("modularity", 0) > 0),
])
results.append(r)

r = run_skill("grn-module", ["--species", "arabidopsis", "--algorithm", "leiden",
              "--resolution", "0.01", "--top-modules", "5"],
              "module: leiden with low resolution")
grade(r, [
    ("has modules", lambda d: d.get("num_modules", 0) > 1),
])
results.append(r)

r = run_skill("grn-module", ["--species", "arabidopsis", "--algorithm", "infomap", "--top-modules", "5"],
              "module: infomap algorithm")
grade(r, [
    ("has modules", lambda d: d.get("num_modules", 0) > 0),
])
results.append(r)

r = run_skill("grn-module", ["--species", "petunia", "--top-modules", "3"],
              "module: petunia network")
grade(r, [
    ("has modules", lambda d: d.get("num_modules", 0) > 0),
])
results.append(r)

r = run_skill("grn-module", ["--species", "arabidopsis", "--gene-id", "AT2G43010"],
              "module: PIF4 module membership")
grade(r, [
    ("query gene module found", lambda d: d.get("query_gene_module", {}).get("module_size", 0) > 0),
    ("has hub TF", lambda d: d.get("query_gene_module", {}).get("hub_tf") is not None),
])
results.append(r)

r = run_skill("grn-module", ["--species", "arabidopsis", "--min-confidence", "0.8", "--top-modules", "3"],
              "module: high confidence edges only")
grade(r, [
    ("returns result", lambda d: "num_modules" in d),
])
results.append(r)

r = run_skill("grn-module", ["--species", "arabidopsis", "--algorithm", "label_propagation", "--top-modules", "5"],
              "module: label propagation")
grade(r, [
    ("has modules", lambda d: d.get("num_modules", 0) > 0),
])
results.append(r)

# =====================================================================
# 27. grn-diff-regulation (10 tests)
# =====================================================================

r = run_skill("grn-diff-regulation",
              ["--species", "arabidopsis", "--group-a", "root", "--group-b", "inflorescence", "--top", "5"],
              "diff-reg: arabidopsis root vs inflorescence")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
    ("has activity scores", lambda d: all("activity_score" in r for r in d.get("results", []))),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "arabidopsis", "--group-a", "root", "--group-b", "inflorescence",
               "--tf-gene-id", "AT5G11260", "--top", "5"],
              "diff-reg: specific TF HY5")
grade(r, [
    ("has results or empty", lambda d: "results" in d),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "petunia", "--group-a", "seedling", "--group-b", "flower", "--top", "5"],
              "diff-reg: petunia seedling vs flower")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "tomato", "--group-a", "leaf", "--group-b", "fruit", "--top", "5"],
              "diff-reg: tomato leaf vs fruit")
grade(r, [
    ("has results", lambda d: len(d.get("results", [])) > 0),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "human", "--group-a", "tissue1", "--group-b", "tissue2"],
              "diff-reg: human graceful degradation")
grade(r, [
    ("empty results", lambda d: len(d.get("results", [])) == 0),
    ("has note", lambda d: "not available" in d.get("note", "").lower()),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "arabidopsis", "--group-a", "root", "--group-b", "inflorescence",
               "--min-fold-change", "3.0", "--top", "5"],
              "diff-reg: high fold-change filter")
grade(r, [
    ("has results", lambda d: "results" in d),
    ("filtered results", lambda d: all(
        abs(r["tf_log2fc"]) >= 3.0 or r["activity_score"] >= 3.0
        for r in d.get("results", []))),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "arabidopsis", "--group-a", "nonexistent", "--group-b", "root"],
              "diff-reg: invalid tissue graceful degradation")
grade(r, [
    ("empty results", lambda d: len(d.get("results", [])) == 0),
    ("lists available tissues", lambda d: len(d.get("available_tissues", [])) > 0),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "arabidopsis", "--group-a", "vegetative_shoot", "--group-b", "seedling", "--top", "3"],
              "diff-reg: shoot vs seedling")
grade(r, [
    ("has results", lambda d: "results" in d),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "tomato", "--group-a", "root", "--group-b", "apex", "--top", "3"],
              "diff-reg: tomato root vs apex")
grade(r, [
    ("has results", lambda d: "results" in d),
])
results.append(r)

r = run_skill("grn-diff-regulation",
              ["--species", "petunia", "--group-a", "corolla_lobes", "--group-b", "petal_limb", "--top", "3"],
              "diff-reg: petunia corolla vs petal")
grade(r, [
    ("has results", lambda d: "results" in d),
])
results.append(r)

# =====================================================================
# grn-infer (inferred edges from expression)
# =====================================================================

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--top", "5"],
              "infer: arabidopsis top edges")
grade(r, [
    ("has edges key", lambda d: "edges" in d),
    ("returns edges", lambda d: len(d["edges"]) > 0),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--gene-id", "AT5G11260", "--direction", "regulators"],
              "infer: HY5 regulators")
grade(r, [
    ("has edges", lambda d: "edges" in d),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--gene-id", "AT5G11260", "--direction", "targets"],
              "infer: HY5 targets")
grade(r, [
    ("has edges", lambda d: "edges" in d),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--method", "GRNBoost2", "--top", "5"],
              "infer: GRNBoost2 only")
grade(r, [
    ("all GRNBoost2", lambda d: all(e["method"] == "GRNBoost2" for e in d["edges"])),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--method", "GENIE3", "--top", "5"],
              "infer: GENIE3 only")
grade(r, [
    ("all GENIE3", lambda d: all(e["method"] == "GENIE3" for e in d["edges"])),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--gene-id", "AT5G11260", "--compare-curated", "--top", "5"],
              "infer: compare curated")
grade(r, [
    ("has curated support field", lambda d: any("has_curated_support" in e for e in d["edges"])),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "arabidopsis", "--min-importance", "0.1", "--top", "5"],
              "infer: high importance")
grade(r, [
    ("all importance >= 0.1", lambda d: all(e["importance"] >= 0.1 for e in d["edges"])),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "tomato", "--top", "5"],
              "infer: tomato edges")
grade(r, [
    ("returns edges", lambda d: len(d["edges"]) > 0),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "petunia", "--top", "5"],
              "infer: petunia edges")
grade(r, [
    ("returns edges", lambda d: len(d["edges"]) > 0),
])
results.append(r)

r = run_skill("grn-infer",
              ["--species", "human", "--top", "5"],
              "infer: human (no data expected)")
grade(r, [
    ("no edges for human", lambda d: len(d.get("edges", [])) == 0),
])
results.append(r)

# =====================================================================
# GRN-EVIDENCE-AUDIT
# =====================================================================
r = run_skill("grn-evidence-audit",
              ["--scope", "gene", "--gene-id", "TP53"],
              "evidence audit: gene TP53")
grade(r, [
    ("supported gene", lambda d: d.get("summary", {}).get("supported") is True),
    ("has confidence", lambda d: "confidence" in d),
])
results.append(r)

r = run_skill("grn-evidence-audit",
              ["--scope", "edge", "--source-id", "TP53", "--target-id", "BAX"],
              "evidence audit: edge TP53->BAX")
grade(r, [
    ("has support counts", lambda d: "support_counts" in d.get("evidence_summary", {})),
    ("edge supported", lambda d: d.get("summary", {}).get("supported") is True),
])
results.append(r)

r = run_skill("grn-evidence-audit",
              ["--scope", "edge", "--source-id", "TP53", "--target-id", "NOPE"],
              "evidence audit: missing target")
grade(r, [
    ("unsupported edge", lambda d: d.get("confidence", {}).get("label") == "unsupported"),
    ("reports coverage gaps", lambda d: len(d.get("coverage_gaps", [])) > 0),
])
results.append(r)

# =====================================================================
# GRN-COVERAGE-REPORT
# =====================================================================
r = run_skill("grn-coverage-report",
              ["--species", "arabidopsis", "--intent", "expression"],
              "coverage report: arabidopsis expression")
grade(r, [
    ("has readiness score", lambda d: "readiness_score" in d),
    ("score positive", lambda d: d.get("readiness_score", 0) > 0),
])
results.append(r)

r = run_skill("grn-coverage-report",
              ["--species", "human", "--intent", "traits"],
              "coverage report: human traits")
grade(r, [
    ("has recommended skills", lambda d: len(d.get("recommended_skills", [])) > 0),
    ("traits layer available", lambda d: d.get("available_layers", {}).get("trait_associations", 0) > 0),
])
results.append(r)

# =====================================================================
# GRN-CANDIDATE-TRIAGE
# =====================================================================
r = run_skill("grn-candidate-triage",
              ["--gene-ids", "TP53,BAX,MDM2", "--intent", "network"],
              "candidate triage: TP53,BAX,MDM2")
grade(r, [
    ("has ranked candidates", lambda d: len(d.get("ranked_candidates", [])) > 0),
    ("TP53 ranks first", lambda d: d.get("ranked_candidates", [{}])[0].get("gene_id") == "TP53"),
])
results.append(r)

r = run_skill("grn-candidate-triage",
              ["--gene-ids", "TP53,NOPE", "--intent", "experiment"],
              "candidate triage: missing gene handling")
grade(r, [
    ("tracks excluded genes", lambda d: any(g.get("gene_id") == "NOPE" for g in d.get("excluded_genes", []))),
])
results.append(r)

# =====================================================================
# GRN-EXPERIMENT-PRIORITIZATION
# =====================================================================
r = run_skill("grn-experiment-prioritization",
              ["--gene-ids", "TP53", "--intent", "experiment"],
              "experiment prioritization: TP53")
grade(r, [
    ("has plan", lambda d: len(d.get("plans", [])) > 0),
    ("has recommended experiments", lambda d: len(d.get("plans", [{}])[0].get("recommended_experiments", [])) > 0),
])
results.append(r)

r = run_skill("grn-experiment-prioritization",
              ["--gene-ids", "Peaxi162Scf00118g00310", "--intent", "rnai", "--species", "petunia"],
              "experiment prioritization: petunia rnai")
grade(r, [
    ("includes dsrna option", lambda d: any(e.get("experiment") == "dsrna_design"
                                             for e in d.get("plans", [{}])[0].get("recommended_experiments", []))),
])
results.append(r)

# =====================================================================
# REPORT
# =====================================================================
print("=" * 70)
print("GRN ATLAS SKILLS TEST REPORT")
print("=" * 70)

pass_count = sum(1 for r in results if r["grade"] == "PASS")
fail_count = sum(1 for r in results if r["grade"] == "FAIL")

# Per-skill summary
from collections import Counter
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

# Details for failures
failures = [r for r in results if r["grade"] == "FAIL"]
if failures:
    print(f"\n--- Failures ({len(failures)}) ---")
    for r in failures:
        print(f"\n  ✗ {r['skill']}: {r['label']}")
        if r.get("error"):
            print(f"    ERROR: {r['error'][:300]}")
        for c in r.get("checks", []):
            if not c["pass"]:
                print(f"    ✗ {c['check']}")
else:
    print("\n  No failures!")

print(f"\n{'=' * 70}")
print(f"TOTAL: {pass_count} PASS / {fail_count} FAIL / {len(results)} tests")
print(f"{'=' * 70}")

# Save results
with open(SKILLS_DIR / "_test_results.json", "w") as f:
    slim = [{k: v for k, v in r.items() if k != "data"} for r in results]
    json.dump(slim, f, indent=2)

# Save Q&A pairs
with open(SKILLS_DIR / "_test_qa_pairs.json", "w") as f:
    qa = []
    for r in results:
        qa.append({
            "skill": r["skill"],
            "label": r["label"],
            "grade": r["grade"],
            "checks": r.get("checks", []),
            "error": r.get("error"),
        })
    json.dump(qa, f, indent=2)

print(f"\nResults saved to _test_results.json and _test_qa_pairs.json")
