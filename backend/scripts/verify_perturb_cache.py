#!/usr/bin/env python3
"""Does memoising get_targets within one request give identical results, faster?

173,337 get_targets calls over ~17,600 distinct genes is ~10x redundancy, and
those calls are 94% of a perturbation run. A per-request cache should remove the
redundancy without changing any result. This verifies "without changing any
result" before anything in main.py is touched.

Runs the cached cascade first, then the current one, and compares exactly.

    backend/venv/bin/python backend/scripts/verify_perturb_cache.py
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
import main  # noqa: E402

GENE, DEPTH, MIN_EFFECT, MIN_CONF = "TP53", 4, 0.05, 0.0


def cascade(db, use_cache):
    """main.perturb's loop verbatim; the only change is the memo."""
    g = db.get_gene(GENE)
    seeds = {g.id: (-1, g.symbol)}
    best, calls = {}, 0
    cache = {}
    frontier = [(gid, s, 1.0, 0, [sym], False, False)
                for gid, (s, sym) in seeds.items()]

    def targets_for(gid):
        nonlocal calls
        if use_cache:
            hit = cache.get(gid)
            if hit is not None:
                return hit
        calls += 1
        rows = db.get_targets(gid, min_confidence=MIN_CONF, include_inferred=True)
        # Keep only what the loop reads, with the Inferred scan done once per
        # edge instead of once per traversal.
        lite = [(t.id, t.symbol, main._EDGE_SIGN.get(t.regulation_type, 0),
                 t.confidence,
                 any(str(s).startswith("Inferred") for s in t.source_databases))
                for t in rows]
        if use_cache:
            cache[gid] = lite
        return lite

    while frontier:
        gid, sign, mag, level, path, inf, unknown = frontier.pop()
        if level >= DEPTH:
            continue
        for tid, tsym, esign, tconf, t_inf in targets_for(gid):
            n_unknown = unknown or esign == 0
            n_sign = sign * (esign if esign else 1)
            n_mag = mag * max(tconf, 0.01) * main._PERTURB_DECAY
            n_inf = inf or t_inf
            if n_mag < MIN_EFFECT:
                continue
            prev = best.get(tid)
            if tid not in seeds and (prev is None or n_mag > prev["magnitude"]):
                best[tid] = {"symbol": tsym, "magnitude": round(n_mag, 4),
                             "sign": n_sign, "unknown": n_unknown,
                             "level": level + 1, "path": path + [tsym],
                             "uses_inferred": n_inf}
            if prev is None or n_mag > prev["magnitude"]:
                frontier.append((tid, n_sign, n_mag, level + 1,
                                 path + [tsym], n_inf, n_unknown))
    return best, calls


def main_():
    db = main.db
    print("=" * 70)
    t0 = time.perf_counter()
    cached, c_calls = cascade(db, True)
    t_cached = time.perf_counter() - t0
    print(f"  cached   {t_cached:7.1f}s   {c_calls:>8,} get_targets calls   "
          f"{len(cached):,} genes")

    t0 = time.perf_counter()
    plain, p_calls = cascade(db, False)
    t_plain = time.perf_counter() - t0
    print(f"  current  {t_plain:7.1f}s   {p_calls:>8,} get_targets calls   "
          f"{len(plain):,} genes")

    print("-" * 70)
    same = cached == plain
    print(f"  results identical: {same}")
    if not same:
        only_c = set(cached) - set(plain)
        only_p = set(plain) - set(cached)
        diff = [k for k in set(cached) & set(plain) if cached[k] != plain[k]]
        print(f"    only in cached {len(only_c)}, only in current {len(only_p)}, "
              f"differing {len(diff)}")
        for k in diff[:3]:
            print(f"    {k}: cached={cached[k]} current={plain[k]}")
    print(f"  speedup: {t_plain/t_cached:.1f}x   "
          f"calls cut {p_calls/max(c_calls,1):.1f}x")
    if same and t_plain / t_cached > 2:
        print(f"\n  -> safe and worth doing. A 156 s run becomes about "
              f"{156*t_cached/t_plain:.0f} s, under the 120 s suite timeout.")
    elif not same:
        print("\n  -> do NOT apply: the cache changes results. Investigate first.")
    print("=" * 70)


if __name__ == "__main__":
    main_()
