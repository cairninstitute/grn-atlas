#!/usr/bin/env python3
"""Is grn-dynamics still usable for Arabidopsis after 1C, and on which genes?

1C left Arabidopsis with far fewer observed signed edges. If connected modules
still exist, the failing test should be re-pointed at a real one rather than
relaxed. If none exist, that is a capability loss worth recording.

    backend/venv/bin/python backend/scripts/find_signed_modules.py
"""
import sqlite3
from collections import defaultdict, deque
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "backend/data/grn.sqlite3"
SPECIES = "arabidopsis"
OBSERVED = ("measured", "perturbation")
MIN_CONF = 0.5


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    q = ",".join("?" for _ in OBSERVED)
    rows = conn.execute(
        f"SELECT i.source_id, i.target_id FROM interactions i "
        f"JOIN genes s ON s.id = i.source_id JOIN genes t ON t.id = i.target_id "
        f"WHERE s.species = ? AND t.species = ? AND i.sign IS NOT NULL "
        f"AND i.sign_evidence IN ({q}) AND i.confidence >= ?",
        (SPECIES, SPECIES, *OBSERVED, MIN_CONF)).fetchall()
    print("=" * 68)
    print(f"{SPECIES}: {len(rows):,} observed signed edges after 1C")
    if not rows:
        print("  -> no observed signed edges at all; dynamics cannot run here")
        return

    adj, nodes = defaultdict(set), set()
    deg = defaultdict(int)
    for a, b in rows:
        adj[a].add(b); adj[b].add(a)
        nodes |= {a, b}
        deg[a] += 1; deg[b] += 1
    print(f"   spanning {len(nodes):,} genes")

    # Connected components, largest first.
    seen, comps = set(), []
    for start in nodes:
        if start in seen:
            continue
        comp, dq = {start}, deque([start])
        while dq:
            x = dq.popleft()
            for y in adj[x]:
                if y not in comp:
                    comp.add(y); dq.append(y)
        seen |= comp
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    big = [c for c in comps if len(c) >= 5]
    print(f"   {len(comps):,} connected modules; {len(big)} with 5+ genes")
    print(f"   largest: {len(comps[0])} genes")

    if not big:
        print("\n  -> no module of 5+ genes. The dynamics test should accept a")
        print("     zero-signed-edge result rather than be re-pointed.")
        return

    # Pick a module and take its best-connected genes, so the subgraph the
    # skill receives actually carries signed edges between the chosen genes.
    comp = big[0]
    picked = sorted(comp, key=lambda g: (-deg[g], g))[:7]
    internal = sum(1 for a, b in rows if a in set(picked) and b in set(picked))
    print(f"\n  candidate gene set (top 7 by degree in a {len(comp)}-gene module):")
    print(f"    {','.join(picked)}")
    print(f"    signed edges strictly among those 7: {internal}")
    if internal == 0:
        print("    (none internal — widening to a tight neighbourhood instead)")
        hub = picked[0]
        nbrs = sorted(adj[hub], key=lambda g: (-deg[g], g))[:6]
        picked = [hub] + nbrs
        internal = sum(1 for a, b in rows if a in set(picked) and b in set(picked))
        print(f"    {','.join(picked)}")
        print(f"    signed edges strictly among those: {internal}")
    conn.close()
    print("=" * 68)


if __name__ == "__main__":
    main()
