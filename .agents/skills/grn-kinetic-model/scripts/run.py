#!/usr/bin/env python3
"""Simulate a signed regulatory circuit as a Hill-function ODE system."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[4] / "backend"
DB = BACKEND / "data" / "grn.sqlite3"

ALPHA = 10.0
K = 1.0
BASAL = 0.05
N_ICS = 4
SEED = 42


def load_circuit(conn: sqlite3.Connection, gene_ids: list[str], species: str | None) -> dict:
    gene_set = set(gene_ids)
    if species is None:
        row = conn.execute("SELECT species FROM genes WHERE id=?", (gene_ids[0],)).fetchone()
        species = row[0] if row else "unknown"

    edges = []
    for row in conn.execute(
        "SELECT source_id, target_id, sign FROM interactions "
        "WHERE sign IS NOT NULL"
    ):
        src, tgt, sign = row
        if src in gene_set and tgt in gene_set:
            edges.append({"source": src, "target": tgt, "sign": sign})

    activators: dict[str, list[str]] = {g: [] for g in gene_ids}
    repressors: dict[str, list[str]] = {g: [] for g in gene_ids}
    for e in edges:
        if e["sign"] == "activation":
            activators[e["target"]].append(e["source"])
        elif e["sign"] == "repression":
            repressors[e["target"]].append(e["source"])

    return {
        "species": species,
        "genes": gene_ids,
        "edges": edges,
        "activators": activators,
        "repressors": repressors,
    }


def rk4_step(state: np.ndarray, dt: float, derivs_fn) -> np.ndarray:
    k1 = derivs_fn(state)
    k2 = derivs_fn(state + 0.5 * dt * k1)
    k3 = derivs_fn(state + 0.5 * dt * k2)
    k4 = derivs_fn(state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def simulate(circuit: dict, hill: float, deg: float, t_end: float, dt: float,
             initial: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    genes = circuit["genes"]
    n = len(genes)
    idx = {g: i for i, g in enumerate(genes)}

    def derivs(x: np.ndarray) -> np.ndarray:
        dx = np.zeros(n)
        for i, g in enumerate(genes):
            prod = BASAL
            act_sum = 0.0
            for a in circuit["activators"][g]:
                xa = max(x[idx[a]], 0.0)
                act_sum += ALPHA * xa**hill / (K**hill + xa**hill)
            rep_prod = 1.0
            for r in circuit["repressors"][g]:
                xr = max(x[idx[r]], 0.0)
                rep_prod *= K**hill / (K**hill + xr**hill)
            prod += act_sum * rep_prod if act_sum > 0 else BASAL * rep_prod
            dx[i] = prod - deg * max(x[i], 0.0)
        return dx

    steps = int(t_end / dt)
    times = np.linspace(0, t_end, steps + 1)
    states = np.zeros((steps + 1, n))
    states[0] = initial
    for t in range(steps):
        states[t + 1] = rk4_step(states[t], dt, derivs)
        states[t + 1] = np.maximum(states[t + 1], 0.0)
    return times, states


def classify_trajectory(times: np.ndarray, states: np.ndarray) -> dict:
    n = states.shape[1]
    tail_start = int(0.7 * len(times))
    tail = states[tail_start:]
    dt = times[1] - times[0]

    osc_genes = 0
    max_amp = 0.0
    best_period = None

    for i in range(n):
        signal = tail[:, i]
        mean_val = np.mean(signal)
        centered = signal - mean_val
        amp = np.max(signal) - np.min(signal)

        if amp < 0.01 * (mean_val + 1e-10):
            continue

        fft_vals = np.abs(np.fft.rfft(centered))
        freqs = np.fft.rfftfreq(len(centered), d=dt)
        if len(fft_vals) < 3:
            continue
        fft_vals[0] = 0
        peak_idx = np.argmax(fft_vals)
        if peak_idx == 0:
            continue
        peak_power = fft_vals[peak_idx]
        noise = np.mean(fft_vals[1:])
        if peak_power > 3 * noise and amp > 0.05:
            osc_genes += 1
            if amp > max_amp:
                max_amp = amp
                best_period = 1.0 / freqs[peak_idx] if freqs[peak_idx] > 0 else None

    return {
        "oscillating_genes": osc_genes,
        "max_amplitude": round(float(max_amp), 4),
        "period": round(float(best_period), 2) if best_period else None,
    }


def sweep(circuit: dict, hills: list[float], degs: list[float],
          t_end: float, dt: float) -> list[dict]:
    n = len(circuit["genes"])
    rng = np.random.RandomState(SEED)
    results = []

    for hill in hills:
        for deg in degs:
            ic_results = []
            steady_states = []

            for ic_idx in range(N_ICS):
                initial = rng.uniform(0.1, 5.0, n)
                times, states = simulate(circuit, hill, deg, t_end, dt, initial)
                info = classify_trajectory(times, states)
                ic_results.append(info)
                final = states[-1].tolist()
                steady_states.append(final)

            n_osc = sum(1 for r in ic_results if r["oscillating_genes"] > 0)
            unique_ss = []
            for ss in steady_states:
                is_new = True
                for uss in unique_ss:
                    if all(abs(a - b) < 0.1 for a, b in zip(ss, uss)):
                        is_new = False
                        break
                if is_new:
                    unique_ss.append(ss)

            if n_osc >= 2:
                classification = "oscillatory"
            elif len(unique_ss) > 1 and n_osc == 0:
                classification = "bistable"
            else:
                classification = "monostable"

            best_osc = max(ic_results, key=lambda r: r["max_amplitude"])
            results.append({
                "hill": hill,
                "degradation": deg,
                "classification": classification,
                "oscillatory_ics": n_osc,
                "distinct_steady_states": len(unique_ss),
                "max_amplitude": best_osc["max_amplitude"],
                "period": best_osc["period"],
            })

    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--genes", required=True, help="Comma-separated gene IDs")
    parser.add_argument("--species", default=None)
    parser.add_argument("--hill-range", default="1,2,4,8")
    parser.add_argument("--deg-range", default="0.1,0.5,1.0,2.0")
    parser.add_argument("--time", type=float, default=100.0)
    parser.add_argument("--dt", type=float, default=0.1)
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()

    gene_ids = [g.strip() for g in args.genes.split(",")]
    hills = [float(x) for x in args.hill_range.split(",")]
    degs = [float(x) for x in args.deg_range.split(",")]

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    circuit = load_circuit(conn, gene_ids, args.species)
    conn.close()

    if not circuit["edges"]:
        print(json.dumps({
            "error": "no signed edges found between the given genes",
            "genes": gene_ids,
            "species": circuit["species"],
        }, indent=2))
        return 0

    results = sweep(circuit, hills, degs, args.time, args.dt)

    n_osc = sum(1 for r in results if r["classification"] == "oscillatory")
    n_bi = sum(1 for r in results if r["classification"] == "bistable")
    total = len(results)

    if n_osc > 0:
        overall = "oscillatory"
    elif n_bi > 0:
        overall = "bistable"
    else:
        overall = "monostable"

    best = max(results, key=lambda r: r["max_amplitude"])

    output = {
        "circuit": {
            "species": circuit["species"],
            "genes": circuit["genes"],
            "edges": circuit["edges"],
            "edge_count": len(circuit["edges"]),
        },
        "parameter_sweep": results,
        "summary": {
            "classification": overall,
            "oscillatory_fraction": round(n_osc / total, 3) if total else 0,
            "bistable_fraction": round(n_bi / total, 3) if total else 0,
            "parameters_tested": total,
        },
        "best_oscillation": best if best["classification"] == "oscillatory" else None,
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
