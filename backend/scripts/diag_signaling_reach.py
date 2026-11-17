#!/usr/bin/env python3
"""Is upstream tracing in the signalling layer informative, or does it saturate?

Loads the layer into memory and runs BFS at increasing depth from several
seeds. Measures graph structure, not the skill's code path.

    backend/venv/bin/python backend/scripts/diag_signaling_reach.py
"""
import sqlite3
from collections import defaultdict, deque
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "backend/data/grn.sqlite3"
SEEDS = ["SRC", "JUN", "AKT1", "TP53"]
DEPTHS = (1, 2, 3, 4)


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rev, nodes = defaultdict(list), set()
    for src, tgt, sp in conn.execute(
            "SELECT source_id, target_id, species FROM regulatory_layer_edges"):
        rev[tgt].append(src)
        nodes.add(src); nodes.add(tgt)
    tf = {g for (g,) in conn.execute("SELECT id FROM genes WHERE is_tf = 1")}
    # Low-degree seed: something with exactly one upstream edge.
    low = next((g for g in sorted(rev) if len(rev[g]) == 1), None)
    conn.close()

    n = len(nodes)
    print("=" * 66)
    print(f"layer: {n:,} distinct genes, {sum(len(v) for v in rev.values()):,} edges")
    print(f"{'seed':<10} " + " ".join(f"d{d}>{'':<7}" for d in DEPTHS) + " saturation")

    for seed in dict.fromkeys(SEEDS + ([low] if low else [])):
        if seed not in nodes:
            print(f"{seed:<10} not in layer"); continue
        seen, frontier, counts = {seed}, [seed], []
        for d in range(1, max(DEPTHS) + 1):
            nxt = [s for node in frontier for s in rev.get(node, []) if s not in seen]
            seen.update(nxt); frontier = list(dict.fromkeys(nxt))
            if d in DEPTHS:
                counts.append(len(seen) - 1)
        pct = 100.0 * counts[-1] / n if n else 0
        tag = "SATURATED" if pct > 15 else "ok"
        print(f"{seed:<10} " + " ".join(f"{c:<9,}" for c in counts) + f" {pct:5.1f}% {tag}")

    print("-" * 66)
    # How much of the layer is one mutually-reachable blob?
    fwd = defaultdict(list)
    for t, ss in rev.items():
        for s in ss:
            fwd[s].append(t)
    seen, big = set(), 0
    for start in nodes:
        if start in seen:
            continue
        comp, q = {start}, deque([start])
        while q:
            x = q.popleft()
            for y in fwd.get(x, []) + rev.get(x, []):
                if y not in comp:
                    comp.add(y); q.append(y)
        seen |= comp
        big = max(big, len(comp))
    print(f"largest weakly-connected component: {big:,} genes "
          f"({100.0*big/n:.1f}% of layer)")
    print(f"TFs in layer: {len(nodes & tf):,}")
    print("=" * 66)


if __name__ == "__main__":
    main()
