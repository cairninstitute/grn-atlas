#!/usr/bin/env python3
"""Verify grn-signaling-layer against raw SQL, and close open questions.

    backend/venv/bin/python backend/scripts/verify_signaling_layer.py
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / ".agents/skills/grn-signaling-layer/scripts/run.py"
DB = ROOT / "backend/data/grn.sqlite3"


def call(*a):
    r = subprocess.run([sys.executable, str(RUNNER), *a],
                       capture_output=True, text=True, cwd=ROOT)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"_error": (r.stderr or r.stdout).strip().splitlines()[-1:] or ["?"]}


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    q = lambda s, *p: conn.execute(s, p).fetchone()[0]

    print("=" * 70)
    print("PER-SPECIES LAYER SIZE")
    for sp, n in conn.execute("SELECT species, COUNT(*) FROM regulatory_layer_edges "
                              "GROUP BY species ORDER BY 2 DESC"):
        genes = q("SELECT COUNT(*) FROM (SELECT source_id g FROM regulatory_layer_edges "
                  "WHERE species=? UNION SELECT target_id FROM regulatory_layer_edges "
                  "WHERE species=?)", sp, sp)
        print(f"  {sp:8} {n:>7,} edges  {genes:>6,} genes")

    collide = q("SELECT COUNT(*) FROM (SELECT g FROM (SELECT source_id g, species FROM "
                "regulatory_layer_edges UNION SELECT target_id, species FROM "
                "regulatory_layer_edges) GROUP BY g HAVING COUNT(DISTINCT species) > 1)")
    print(f"  ids present in BOTH species: {collide:,}"
          f"{'  <- species-less queries mix them' if collide else '  (none)'}")

    print("-" * 70)
    print("COUNTS: skill vs raw SQL  (the truncation fix)")
    hubs = [g for g, in conn.execute(
        "SELECT source_id FROM regulatory_layer_edges GROUP BY source_id "
        "ORDER BY COUNT(*) DESC LIMIT 2")]
    bad = 0
    for gene in hubs + ["JUN"]:
        d = call("--gene-id", gene)
        if "_error" in d:
            print(f"  {gene:10} ERROR {d['_error'][0]}"); bad += 1; continue
        sp = d.get("species")
        pred = ("AND species=?", [sp]) if sp else ("", [])
        t_down = q(f"SELECT COUNT(*) FROM regulatory_layer_edges WHERE source_id=? "
                   f"{pred[0]}", gene, *pred[1])
        t_up = q(f"SELECT COUNT(*) FROM regulatory_layer_edges WHERE target_id=? "
                 f"{pred[0]}", gene, *pred[1])
        t_tf = q(f"SELECT COUNT(*) FROM regulatory_layer_edges e JOIN genes g "
                 f"ON g.id=e.target_id WHERE e.source_id=? AND g.is_tf=1 "
                 f"{pred[0].replace('species','e.species')}", gene, *pred[1])
        okd = d["downstream_count"] == t_down
        oku = d["upstream_count"] == t_up
        oktf = d["tf_targets_in_layer"] == t_tf
        bad += (not okd) + (not oku) + (not oktf)
        print(f"  {gene:10} down {d['downstream_count']:>4}/{t_down:<4}{'ok' if okd else 'WRONG'}"
              f"  up {d['upstream_count']:>4}/{t_up:<4}{'ok' if oku else 'WRONG'}"
              f"  tf_tgt {d['tf_targets_in_layer']:>4}/{t_tf:<4}{'ok' if oktf else 'WRONG'}"
              f"  trunc={d['downstream_truncated']}")
    print(f"  -> {'ALL COUNTS MATCH RAW SQL' if not bad else str(bad) + ' MISMATCHES'}")

    print("-" * 70)
    print("TRACE: does it flag its own saturation?")
    for gene in [hubs[0], "JUN"]:
        for depth in (2, 3):
            t = call("--gene-id", gene, "--trace", "--depth", str(depth))
            if "_error" in t:
                print(f"  {gene:8} d{depth} ERROR"); continue
            print(f"  {gene:8} d{depth}  reached {t['reached_count']:>5,}"
                  f"  frac {t['reached_fraction']:>6.1%}"
                  f"  saturated={str(t['saturated']):<5}"
                  f"  edges_capped={t['edges_truncated']}")

    print("-" * 70)
    print("OPEN QUESTION: were the 51 pre-1A layer rows hand-curated?")
    g = subprocess.run(["git", "log", "--all", "--diff-filter=A", "--name-only",
                        "--pretty=format:", "--", "*multilayer*.json"],
                       capture_output=True, text=True, cwd=ROOT)
    found = sorted({l.strip() for l in g.stdout.splitlines() if l.strip()})
    if found:
        print("  manifests ever committed:")
        for f in found[:6]:
            here = "present" if (ROOT / f).exists() else "DELETED from worktree"
            print(f"    {f}  [{here}]")
    else:
        print("  no *multilayer*.json ever committed -> the 51 rows did not come")
        print("  from a tracked manifest; nothing curated was lost.")
    conn.close()
    print("=" * 70)


if __name__ == "__main__":
    main()
