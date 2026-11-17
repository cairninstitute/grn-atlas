#!/usr/bin/env python3
"""Where do grn-perturbation's 156 seconds go?

The database is not the bottleneck: 400 fan-out reads cost under 4 s. This
replicates main.perturb's cascade loop verbatim, with counters, so the cost is
counted rather than inferred. Reads only.

    backend/venv/bin/python backend/scripts/profile_perturb_cascade.py
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
import main  # noqa: E402

GENE, DEPTH, MIN_EFFECT, MIN_CONF = "TP53", 4, 0.05, 0.0


def main_():
    db = main.db
    g = db.get_gene(GENE)
    if g is None:
        print(f"{GENE} not found"); return
    seeds = {g.id: (-1, g.symbol)}
    best = {}
    frontier = [(gid, s, 1.0, 0, [sym], False, False)
                for gid, (s, sym) in seeds.items()]

    pops = edges = pushes = pruned = 0
    db_time = inferred_time = 0.0
    max_frontier = 0
    t_all = time.perf_counter()

    while frontier:
        max_frontier = max(max_frontier, len(frontier))
        gid, sign, mag, level, path, inf, unknown = frontier.pop()
        pops += 1
        if level >= DEPTH:
            continue
        t0 = time.perf_counter()
        targets = db.get_targets(gid, min_confidence=MIN_CONF, include_inferred=True)
        db_time += time.perf_counter() - t0
        for t in targets:
            edges += 1
            esign = main._EDGE_SIGN.get(t.regulation_type, 0)
            n_unknown = unknown or esign == 0
            n_sign = sign * (esign if esign else 1)
            n_mag = mag * max(t.confidence, 0.01) * main._PERTURB_DECAY
            t1 = time.perf_counter()
            n_inf = inf or any(str(s).startswith("Inferred") for s in t.source_databases)
            inferred_time += time.perf_counter() - t1
            if n_mag < MIN_EFFECT:
                pruned += 1
                continue
            prev = best.get(t.id)
            if t.id not in seeds and (prev is None or n_mag > prev["magnitude"]):
                best[t.id] = {"symbol": t.symbol, "magnitude": round(n_mag, 4),
                              "sign": n_sign, "unknown": n_unknown,
                              "level": level + 1, "path": path + [t.symbol],
                              "uses_inferred": n_inf}
            if prev is None or n_mag > prev["magnitude"]:
                frontier.append((t.id, n_sign, n_mag, level + 1,
                                 path + [t.symbol], n_inf, n_unknown))
                pushes += 1
    total = time.perf_counter() - t_all

    print("=" * 70)
    print(f"  {GENE} KO, depth {DEPTH}: {total:.1f}s total")
    print(f"    frontier pops          {pops:>12,}")
    print(f"    get_targets calls      {pops:>12,}  ({db_time:7.1f}s, "
          f"{100*db_time/total:4.1f}% of total)")
    print(f"    edge traversals        {edges:>12,}")
    print(f"    re-pushes onto frontier{pushes:>12,}  "
          f"({pushes/max(pops,1):.1f} per pop)")
    print(f"    pruned by min_effect   {pruned:>12,}")
    print(f"    peak frontier size     {max_frontier:>12,}")
    print(f"    distinct genes affected{len(best):>12,}")
    print(f"    'Inferred' string scan {inferred_time:>11.1f}s  "
          f"({100*inferred_time/total:4.1f}% of total)")
    py = total - db_time
    print(f"\n  database {100*db_time/total:.0f}%, Python {100*py/total:.0f}%")
    if pushes > pops * 0.5:
        print(f"  -> nodes are re-expanded whenever a stronger route appears, with")
        print(f"     no visited bound: {pushes:,} pushes for {len(best):,} genes.")
    print("=" * 70)


if __name__ == "__main__":
    main_()
