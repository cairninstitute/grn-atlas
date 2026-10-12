#!/usr/bin/env python3
"""Generate the atlas-backed Arabidopsis circadian-clock demonstration."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Circle, FancyArrowPatch
from PIL import Image

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
OUT = ROOT / "public" / "circadian-clock-demo"
sys.path.insert(0, str(BACKEND))

import circadian_clock as clock  # noqa: E402
import main as backend  # noqa: E402


INK = "#132A32"
MUTED = "#60747A"
PAPER = "#F4F0E7"
GRID = "#D8D2C5"
ACTIVATE = "#16877A"
REPRESS = "#CB5548"
CYAN = "#00A7B5"
GOLD = "#E8AF36"
SLATE = "#D8E0DF"
GENE_COLORS = {
    "CCA1": "#007D8A", "LHY": "#319D9B", "RVE8": "#75B9A7",
    "PRR9": "#D8A229", "PRR7": "#E18437", "PRR5": "#D35E3F",
    "ZTL": "#A34B46", "GI": "#6C5A9A", "TOC1": "#48548E",
    "ELF3": "#344B70", "ELF4": "#445F7D", "LUX": "#5A6F8D",
}
ACTIVITY_CMAP = LinearSegmentedColormap.from_list("clock", [SLATE, "#F8D879", GOLD])


def _phase_positions(simulation):
    positions = {}
    phases = {}
    # Keep the biologically ordered genes legible on a clock face. Exact model
    # phases remain in the trajectories and evidence manifest; the network ring
    # communicates order, not quantitative peak time.
    for display_index, gene in enumerate(clock.CLOCK_GENES):
        phase = clock.peak_phase_hours(simulation, gene.symbol)
        display_hour = display_index * 24.0 / len(clock.CLOCK_GENES)
        theta = np.pi / 2.0 - 2.0 * np.pi * display_hour / 24.0
        positions[gene.symbol] = (1.05 * np.cos(theta), 1.05 * np.sin(theta))
        phases[gene.symbol] = phase
    return positions, phases


def _draw_network(ax, activities, edges, positions, zt, title=True):
    ax.clear()
    ax.set_facecolor(PAPER)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.55, 1.55)
    ax.set_ylim(-1.58, 1.5)

    for edge in edges:
        source, target = edge["source"], edge["target"]
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        reciprocal = any(e["source"] == target and e["target"] == source for e in edges)
        bend = 0.16 if reciprocal and source < target else -0.16 if reciprocal else 0.05
        color = ACTIVATE if edge["sign"] == "activation" else REPRESS
        alpha = 0.14 + 0.68 * activities[source]
        arrow = "-|>" if edge["sign"] == "activation" else "-["
        patch = FancyArrowPatch(
            (x1, y1), (x2, y2), connectionstyle=f"arc3,rad={bend}",
            arrowstyle=arrow, mutation_scale=12, color=color,
            linewidth=0.8 + 1.1 * float(edge["confidence"]), alpha=alpha,
            shrinkA=19, shrinkB=19, zorder=1,
        )
        ax.add_patch(patch)

    for symbol, (x, y) in positions.items():
        activity = float(activities[symbol])
        circle = Circle((x, y), 0.16, facecolor=ACTIVITY_CMAP(activity),
                        edgecolor=INK, linewidth=1.4, zorder=3)
        ax.add_patch(circle)
        ax.text(x, y + 0.015, symbol, ha="center", va="center", color=INK,
                fontsize=8.5, fontweight="bold", zorder=4)

    hand_theta = np.pi / 2.0 - 2.0 * np.pi * (zt % 24.0) / 24.0
    ax.add_patch(Circle((0, 0), 0.34, facecolor=PAPER, edgecolor=GRID,
                        linewidth=1.2, zorder=4))
    ax.plot([0, 0.24 * np.cos(hand_theta)], [0, 0.24 * np.sin(hand_theta)],
            color=INK, linewidth=2.2, zorder=5)
    ax.add_patch(Circle((0, 0), 0.025, facecolor=INK, edgecolor="none", zorder=6))
    ax.text(0, -0.16, f"ZT {zt % 24:04.1f}", ha="center", va="center",
            color=MUTED, fontsize=8, fontweight="bold", zorder=6)
    if title:
        ax.text(-1.48, 1.40, "DARWIN EVIDENCE LAYER", color=CYAN, fontsize=9,
                fontweight="bold", ha="left")
        ax.text(-1.48, 1.25, "Measured signed clock edges", color=INK, fontsize=16,
                fontweight="bold", ha="left")
        ax.text(-1.48, -1.38, "edge brightness follows regulator activity",
                color=MUTED, fontsize=8, ha="left")
        ax.text(-1.48, -1.50, "ring shows phase order · traces show quantitative timing",
                color=MUTED, fontsize=8, ha="left")


def _shade_subjective_night(ax, start=0, stop=72):
    day = 0
    while day * 24 < stop:
        ax.axvspan(day * 24 + 12, day * 24 + 24, color="#DCE4E5", alpha=0.55, lw=0)
        day += 1


def _plot_timeseries(ax, simulation, genes, stop=72, title=None):
    _shade_subjective_night(ax, stop=stop)
    for symbol in genes:
        ax.plot(simulation["time"], simulation["genes"][symbol],
                color=GENE_COLORS[symbol], linewidth=2.0, label=symbol)
    ax.set_xlim(0, stop)
    ax.set_ylim(-0.03, 1.08)
    ax.set_xticks(np.arange(0, stop + 1, 12))
    ax.set_yticks([0, 0.5, 1])
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.set_xlabel("hours from subjective dawn", color=MUTED, fontsize=9)
    ax.set_ylabel("normalized activity", color=MUTED, fontsize=9)
    if title:
        ax.set_title(title, loc="left", color=INK, fontsize=14, fontweight="bold", pad=8)
    ax.legend(frameon=False, ncol=3, fontsize=8, loc="upper right")


def _write_csv(path, wild_type, overexpression):
    symbols = [gene.symbol for gene in clock.CLOCK_GENES]
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["condition", "time_hours", *symbols])
        for condition, simulation in (("wild_type", wild_type), ("cca1_ox_proxy", overexpression)):
            for index, time in enumerate(simulation["time"]):
                writer.writerow([condition, f"{time:.2f}", *(
                    f"{simulation['genes'][symbol][index]:.6f}" for symbol in symbols
                )])


def _write_static(path, wild_type, overexpression, edges, positions):
    fig = plt.figure(figsize=(15, 9), facecolor=PAPER)
    grid = fig.add_gridspec(2, 2, width_ratios=[0.92, 1.35], height_ratios=[1, 1],
                           wspace=0.18, hspace=0.34)
    network_ax = fig.add_subplot(grid[:, 0])
    activities = {symbol: values[0] for symbol, values in wild_type["genes"].items()}
    _draw_network(network_ax, activities, edges, positions, 0.0)

    wt_ax = fig.add_subplot(grid[0, 1])
    _plot_timeseries(wt_ax, wild_type, ["CCA1", "PRR9", "PRR7", "PRR5", "TOC1", "LUX"],
                     title=f"A {wild_type['period_hours']:.1f}-hour free-running limit cycle")

    ox_ax = fig.add_subplot(grid[1, 1])
    _shade_subjective_night(ox_ax)
    for symbol in ("CCA1", "LUX"):
        ox_ax.plot(wild_type["time"], wild_type["genes"][symbol],
                   color=GENE_COLORS[symbol], linewidth=1.5, alpha=0.35)
        ox_ax.plot(overexpression["time"], overexpression["genes"][symbol],
                   color=GENE_COLORS[symbol], linewidth=2.4, label=f"{symbol} · CCA1-OX proxy")
    ox_ax.axvline(24, color=REPRESS, linestyle="--", linewidth=1.5)
    ox_ax.text(24.8, 1.01, "morning module clamped high", color=REPRESS, fontsize=8,
               va="top")
    ox_ax.set_xlim(0, 72)
    ox_ax.set_ylim(-0.03, 1.08)
    ox_ax.set_xticks(np.arange(0, 73, 12))
    ox_ax.set_yticks([0, 0.5, 1])
    ox_ax.grid(axis="y", color=GRID, linewidth=0.7)
    ox_ax.spines[["top", "right", "left"]].set_visible(False)
    ox_ax.spines["bottom"].set_color(GRID)
    ox_ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ox_ax.set_xlabel("hours from subjective dawn", color=MUTED, fontsize=9)
    ox_ax.set_ylabel("normalized activity", color=MUTED, fontsize=9)
    ox_ax.set_title("Perturbation test: oscillation collapses after a CCA1-OX proxy",
                    loc="left", color=INK, fontsize=14, fontweight="bold", pad=8)
    ox_ax.legend(frameon=False, fontsize=8, loc="upper right")

    fig.suptitle("Arabidopsis clock · evidence and dynamics kept separate",
                 x=0.04, y=0.985, ha="left", color=INK, fontsize=20, fontweight="bold")
    fig.text(0.04, 0.945,
             f"{len(clock.CLOCK_GENES)} atlas-resolved genes  ·  {len(edges)} measured signed edges  ·  "
             "continuous three-module demonstration model",
             color=MUTED, fontsize=10)
    fig.text(0.04, 0.018,
             "Solid edges: GRN Atlas evidence. Trajectories: literature-structured explanatory model, not fitted expression data.",
             color=MUTED, fontsize=9)
    fig.savefig(path, dpi=160, facecolor=PAPER, bbox_inches="tight")
    plt.close(fig)


def _write_gif(path, simulation, edges, positions):
    frame_times = np.arange(0, 48.01, 1.0)
    frames = []
    for frame_time in frame_times:
        index = int(np.argmin(np.abs(simulation["time"] - frame_time)))
        activities = {symbol: values[index] for symbol, values in simulation["genes"].items()}
        fig = plt.figure(figsize=(8.2, 8.0), facecolor=PAPER)
        grid = fig.add_gridspec(2, 1, height_ratios=[3.25, 1.1], hspace=0.12)
        network_ax = fig.add_subplot(grid[0])
        _draw_network(network_ax, activities, edges, positions, frame_time)
        trace_ax = fig.add_subplot(grid[1])
        _plot_timeseries(trace_ax, simulation, ["CCA1", "PRR7", "TOC1", "LUX"],
                         stop=48)
        trace_ax.axvline(frame_time, color=INK, linewidth=1.5)
        fig.suptitle("Arabidopsis circadian clock", x=0.07, y=0.985, ha="left",
                     color=INK, fontsize=18, fontweight="bold")
        fig.text(0.07, 0.948,
                 "Darwin signed edges + separate continuous clock model",
                 color=MUTED, fontsize=9)
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=95, facecolor=PAPER, bbox_inches="tight")
        plt.close(fig)
        buffer.seek(0)
        frames.append(Image.open(buffer).convert("RGB"))
    durations = [115] * len(frames)
    durations[0] = durations[-1] = 900
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations,
                   loop=0, disposal=2, optimize=True)


def _write_html(path, stats):
    path.write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Arabidopsis Circadian Clock · Darwin</title>
<style>
:root{{--paper:#f4f0e7;--ink:#132a32;--muted:#60747a;--cyan:#00a7b5;--red:#cb5548}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:Georgia,'Times New Roman',serif}}
main{{max-width:1120px;margin:auto;padding:64px 28px 88px}} .kicker{{font:700 12px/1.2 sans-serif;letter-spacing:.16em;color:var(--cyan)}}
h1{{font-size:clamp(42px,7vw,78px);line-height:.95;max-width:980px;margin:18px 0 24px;letter-spacing:-.04em}}
.lead{{font-size:21px;line-height:1.55;max-width:820px;color:var(--muted)}} img{{width:100%;display:block;border:1px solid #d8d2c5;margin:42px 0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:48px 0}} article{{border-top:4px solid var(--cyan);padding:20px 4px}}
article:last-child{{border-color:var(--red)}} h2{{font-size:27px;margin:0 0 12px}} p,li{{font-size:17px;line-height:1.55}}
.stats{{display:flex;gap:36px;flex-wrap:wrap;margin:32px 0}} .stat strong{{display:block;font:700 34px/1 sans-serif}} .stat span{{font:12px sans-serif;color:var(--muted)}}
a{{color:var(--ink);text-decoration-thickness:1px}} .note{{background:#e6ece9;padding:24px 28px;margin-top:40px}}
@media(max-width:720px){{main{{padding:40px 18px}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="kicker">DARWIN · GRN ATLAS DEMONSTRATION</div>
<h1>A clock needs time, not only wiring.</h1>
<p class="lead">Darwin identifies the Arabidopsis clock genes and retrieves the experimentally signed regulatory edges among them. A separate continuous model adds the delays and feedback needed to demonstrate a repeating circadian rhythm.</p>
<div class="stats"><div class="stat"><strong>{stats['genes']}</strong><span>ATLAS-RESOLVED GENES</span></div><div class="stat"><strong>{stats['edges']}</strong><span>MEASURED SIGNED EDGES</span></div><div class="stat"><strong>{stats['period']:.1f} h</strong><span>MODEL PERIOD</span></div></div>
<img src="clock_demo.gif" alt="Animated Arabidopsis clock network and expression trajectories">
<div class="grid"><article><h2>What Darwin contributes</h2><p>Stable Arabidopsis identifiers, signed edge retrieval, confidence and provenance, plus a Boolean attractor result used as a comparison. The solid arrows in the animation come directly from the rebuilt GRN Atlas database.</p></article><article><h2>What the clock model contributes</h2><p>A compact morning–PRR–evening repressilator supplies continuous activity and delayed negative feedback. It is literature-structured and explanatory, not fitted expression data and not inferred from edge signs alone.</p></article></div>
<img src="clock_demo.png" alt="Static summary of the clock network, wild-type rhythm and CCA1 overexpression proxy">
<div class="note"><strong>Truth boundary.</strong> The wild-type trajectory is a demonstration model. The CCA1-OX panel clamps the combined CCA1/LHY morning module high, so it is a qualitative proxy rather than a genotype-exact prediction. The biologically supported expectation is loss of rhythmicity; the plotted magnitude is not an experimental measurement.</div>
<p><a href="clock_timeseries.csv">Download trajectories (CSV)</a> · <a href="clock_evidence.json">Inspect evidence and assumptions (JSON)</a></p>
</main></body></html>""", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    resolved = clock.resolve_clock_genes(backend.db)
    edges = clock.load_atlas_clock_edges(backend.db)
    wild_type = clock.simulate_clock(hours=72)
    overexpression = clock.simulate_clock(hours=72, perturb_at=24.0)
    positions, phases = _phase_positions(wild_type)

    locus_ids = [gene.locus for gene in clock.CLOCK_GENES]
    boolean_result = asyncio.run(backend.network_dynamics(backend.NetworkDynamicsRequest(
        genes=locus_ids, species="arabidopsis", initial="on", max_steps=50,
    )))
    evidence = {
        "truth_boundary": {
            "atlas": "gene identities and measured/perturbation signed edges",
            "model": "unfitted three-module continuous repressilator with explicit phase assumptions",
            "not_claimed": "GRN Atlas edge signs alone predict a quantitative circadian rhythm",
        },
        "genes": [{
            "symbol": gene.symbol, "locus": gene.locus, "atlas_symbol": resolved[gene.symbol].symbol,
            "module": gene.module, "phase_label": gene.phase_label,
            "model_peak_hours": round(phases[gene.symbol], 2),
        } for gene in clock.CLOCK_GENES],
        "atlas_signed_edges": edges,
        "atlas_edge_sources": dict(Counter(source for edge in edges for source in edge["sources"])),
        "continuous_model": wild_type["model"] | {"period_hours": wild_type["period_hours"]},
        "boolean_comparison": boolean_result,
        "references": [
            {"title": "The clock gene circuit in Arabidopsis includes a repressilator with additional feedback loops", "doi": "10.1038/msb.2012.6"},
            {"title": "Revised Morning Loops of the Arabidopsis Circadian Clock Based on Analyses of Direct Regulatory Interactions", "doi": "10.1371/journal.pone.0143943"},
            {"title": "Constitutive expression of CCA1 disrupts circadian rhythms", "pmid": "9657153", "doi": "10.1016/S0092-8674(00)81464-6"},
        ],
    }
    (OUT / "clock_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    _write_csv(OUT / "clock_timeseries.csv", wild_type, overexpression)
    _write_static(OUT / "clock_demo.png", wild_type, overexpression, edges, positions)
    _write_gif(OUT / "clock_demo.gif", wild_type, edges, positions)
    _write_html(OUT / "index.html", {
        "genes": len(resolved), "edges": len(edges), "period": wild_type["period_hours"],
    })
    print(f"wrote {OUT}")
    print(f"{len(resolved)} genes; {len(edges)} signed atlas edges; period={wild_type['period_hours']:.2f} h")
    print(f"Boolean comparison: {boolean_result['attractor']}")


if __name__ == "__main__":
    main()
