"""Atlas-backed, time-aware Arabidopsis clock demonstration model.

This module deliberately separates two evidence layers:

* GRN Atlas supplies gene identity and measured signed regulatory edges.
* A compact three-module repressilator supplies continuous dynamics.

The repressilator is an explanatory model of morning, PRR/day, and evening
feedback. It is not fitted to GRN Atlas and is not a replacement for the
generic Boolean ``network_dynamics`` endpoint.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ClockGene:
    symbol: str
    locus: str
    module: str
    delay_hours: float
    phase_label: str


# Delays spread each module's activity into the experimentally established
# dawn -> PRR9 -> PRR7 -> PRR5 -> evening ordering. They are illustrative,
# literature-constrained phase assumptions rather than fitted measurements.
CLOCK_GENES = (
    ClockGene("CCA1", "AT2G46830", "morning", 0.0, "dawn"),
    ClockGene("LHY", "AT1G01060", "morning", 0.5, "dawn"),
    ClockGene("RVE8", "AT3G09600", "morning", 3.0, "morning"),
    ClockGene("PRR9", "AT2G46790", "day", -4.0, "early day"),
    ClockGene("PRR7", "AT5G02810", "day", 0.0, "midday"),
    ClockGene("PRR5", "AT5G24470", "day", 3.5, "afternoon"),
    ClockGene("ZTL", "AT5G57360", "day", 2.0, "afternoon"),
    ClockGene("GI", "AT1G22770", "evening", -2.0, "late day"),
    ClockGene("TOC1", "AT5G61380", "evening", 0.0, "evening"),
    ClockGene("ELF3", "AT2G25930", "evening", 0.5, "evening"),
    ClockGene("ELF4", "AT2G40080", "evening", 0.0, "evening"),
    ClockGene("LUX", "AT3G46640", "evening", 1.0, "early night"),
)

MODULE_INDEX = {"morning": 0, "day": 1, "evening": 2}


def resolve_clock_genes(db: Any) -> dict[str, Any]:
    """Resolve every clock component by stable Arabidopsis locus ID."""
    resolved = {}
    for spec in CLOCK_GENES:
        gene = db.get_gene(spec.locus)
        if gene is None or gene.species != "arabidopsis":
            raise LookupError(f"missing Arabidopsis clock gene {spec.symbol} ({spec.locus})")
        resolved[spec.symbol] = gene
    return resolved


def load_atlas_clock_edges(db: Any) -> list[dict[str, Any]]:
    """Return non-self, signed experimental edges among the clock genes."""
    resolved = resolve_clock_genes(db)
    id_to_symbol = {gene.id: symbol for symbol, gene in resolved.items()}
    ids = list(id_to_symbol)
    placeholders = ",".join("?" * len(ids))
    rows = db.conn.execute(
        f"SELECT source_id, target_id, sign, sign_evidence, confidence, sources, pmids "
        f"FROM interactions WHERE source_id IN ({placeholders}) "
        f"AND target_id IN ({placeholders}) AND sign IN ('activation','repression') "
        f"AND sign_evidence IN ('measured','perturbation')",
        ids + ids,
    ).fetchall()
    edges = []
    for source, target, sign, evidence, confidence, sources, pmids in rows:
        if source == target:
            continue
        edges.append({
            "source_id": source,
            "source": id_to_symbol[source],
            "target_id": target,
            "target": id_to_symbol[target],
            "sign": sign,
            "sign_evidence": evidence,
            "confidence": confidence,
            "sources": json.loads(sources or "[]"),
            "pmids": json.loads(pmids or "[]"),
        })
    return sorted(edges, key=lambda edge: (edge["source"], edge["target"]))


def _derivative(state: np.ndarray, alpha: float, hill: float, decay: float,
                basal: float) -> np.ndarray:
    morning, day, evening = state
    return np.array([
        basal + alpha / (1.0 + day**hill) - decay * morning,
        basal + alpha / (1.0 + evening**hill) - decay * day,
        basal + alpha / (1.0 + morning**hill) - decay * evening,
    ])


def _rk4_step(state: np.ndarray, dt: float, alpha: float, hill: float,
              decay: float, basal: float) -> np.ndarray:
    args = (alpha, hill, decay, basal)
    k1 = _derivative(state, *args)
    k2 = _derivative(state + dt * k1 / 2.0, *args)
    k3 = _derivative(state + dt * k2 / 2.0, *args)
    k4 = _derivative(state + dt * k3, *args)
    return np.maximum(0.0, state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0)


def _integrate(initial: np.ndarray, start: float, stop: float, dt: float,
               perturb_at: float | None, clamp_value: float | None,
               alpha: float, hill: float, decay: float, basal: float
               ) -> tuple[np.ndarray, np.ndarray]:
    steps = int(round((stop - start) / dt))
    times = start + np.arange(steps + 1) * dt
    states = np.empty((steps + 1, 3), dtype=float)
    states[0] = initial
    for index in range(steps):
        state = states[index].copy()
        clamped = perturb_at is not None and times[index] >= perturb_at
        if clamped:
            state[0] = float(clamp_value)
        nxt = _rk4_step(state, dt, alpha, hill, decay, basal)
        if clamped or (perturb_at is not None and times[index + 1] >= perturb_at):
            nxt[0] = float(clamp_value)
        states[index + 1] = nxt
    return times, states


def _peak_times(times: np.ndarray, values: np.ndarray) -> np.ndarray:
    mask = (values[1:-1] > values[:-2]) & (values[1:-1] >= values[2:])
    return times[1:-1][mask]


def simulate_clock(hours: float = 72.0, dt: float = 0.05,
                   perturb_at: float | None = None) -> dict[str, Any]:
    """Simulate the compact clock, optionally applying a CCA1-OX proxy.

    The morning-module clamp is applied at ``perturb_at``. CCA1 and LHY are
    grouped in this compact model, so the perturbation is explicitly a CCA1-OX
    proxy rather than a genotype-exact simulation.
    """
    alpha, hill, decay, basal = 10.0, 3.0, 0.30, 0.05
    warm_times, warm_states = _integrate(
        np.array([4.0, 1.0, 0.2]), 0.0, 320.0, dt, None, None,
        alpha, hill, decay, basal,
    )
    peaks = _peak_times(warm_times, warm_states[:, 0])
    if len(peaks) < 3:
        raise RuntimeError("clock model did not reach a stable limit cycle")
    period = float(np.mean(np.diff(peaks[-4:])))
    anchor = float(peaks[-1] - 12.0)
    initial_index = int(round(anchor / dt))
    initial = warm_states[initial_index]
    clamp_value = float(np.max(warm_states[warm_times >= peaks[-2], 0]) * 1.15)
    raw_times, raw_states = _integrate(
        initial, -12.0, hours, dt, perturb_at, clamp_value,
        alpha, hill, decay, basal,
    )
    keep = raw_times >= -1e-9
    times = raw_times[keep]
    states = raw_states[keep]
    raw_modules = {name: raw_states[:, index] for name, index in MODULE_INDEX.items()}

    # Normalize against the wild-type limit-cycle range, never against a
    # perturbed trajectory that may become flat.
    reference = warm_states[warm_times >= peaks[-2]]
    bounds = {
        name: (float(reference[:, index].min()), float(reference[:, index].max()))
        for name, index in MODULE_INDEX.items()
    }
    profiles = {}
    for gene in CLOCK_GENES:
        values = np.interp(
            times - gene.delay_hours,
            raw_times,
            raw_modules[gene.module],
        )
        low, high = bounds[gene.module]
        profiles[gene.symbol] = np.clip((values - low) / (high - low), 0.0, 1.0)

    return {
        "time": times,
        "modules": states,
        "genes": profiles,
        "period_hours": period,
        "perturb_at": perturb_at,
        "clamp_value": clamp_value if perturb_at is not None else None,
        "model": {
            "name": "three-module continuous repressilator",
            "modules": ["CCA1/LHY morning", "PRR daytime", "evening complex"],
            "architecture": "morning represses evening; evening represses PRR; PRR represses morning",
            "parameters": {"alpha": alpha, "hill": hill, "decay_per_hour": decay, "basal": basal},
            "fitted_to_data": False,
            "perturbation_note": "CCA1-OX is represented by clamping the combined morning module high",
        },
    }


def peak_phase_hours(simulation: dict[str, Any], symbol: str) -> float:
    """Return a gene's peak phase in the first modeled circadian period."""
    period = simulation["period_hours"]
    times = simulation["time"]
    values = simulation["genes"][symbol]
    mask = times < period
    phase_times = times[mask]
    phase_values = values[mask]
    if phase_values[0] >= phase_values[1] and phase_values[0] >= 0.99 * phase_values.max():
        return float(phase_times[0])
    peaks = np.flatnonzero(
        (phase_values[1:-1] > phase_values[:-2])
        & (phase_values[1:-1] >= phase_values[2:])
    ) + 1
    index = int(peaks[0]) if len(peaks) else int(np.argmax(phase_values))
    return float(phase_times[index])
