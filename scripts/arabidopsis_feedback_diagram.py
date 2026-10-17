#!/usr/bin/env python3
"""Arabidopsis feedback architecture diagram with exploratory edges.

Generates a transit-map-style diagram showing the mega-core hub structure,
satellite cores, inter-core relationships, and the macro feedback circuit.
"""

from __future__ import annotations

import sqlite3
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from feedback_control import analyze_feedback, FeedbackParameters


COLORS = {
    "measured": "#2563eb",
    "perturbation": "#7c3aed",
    "candidate": "#d97706",
    "unknown": "#94a3b8",
}

EDGE_COLORS = {
    "measured": "#2563eb",
    "perturbation": "#9333ea",
    "candidate": "#ea580c",
}

SIGN_MARKERS = {
    "activation": "→",
    "repression": "⊣",
}


def run():
    db = sqlite3.connect(str(BACKEND / "data" / "grn.sqlite3"))
    db.execute("PRAGMA foreign_keys = ON")
    params = FeedbackParameters(include_candidates=True, include_exploratory=True)
    result = analyze_feedback(db, "arabidopsis", params)

    cores = result["cores"]
    rels = result.get("core_relationships", [])
    macros = result.get("macro_circuits", [])

    gene_ids = []
    for c in cores:
        gene_ids.extend(c.get("_gene_ids", []))
    syms = {}
    for i in range(0, len(gene_ids), 500):
        batch = gene_ids[i:i + 500]
        ph = ",".join("?" for _ in batch)
        for r in db.execute(f"SELECT id, symbol FROM genes WHERE id IN ({ph})", batch):
            syms[r[0]] = r[1]

    mega = cores[0]
    satellites = cores[1:]

    # Count degrees in mega-core backbone
    from collections import Counter
    out_deg, in_deg = Counter(), Counter()
    for e in mega.get("_backbone_edges", []):
        src = e.get("source", e.get("source_id"))
        tgt = e.get("target", e.get("target_id"))
        if src and tgt:
            out_deg[src] += 1
            in_deg[tgt] += 1
    total_deg = Counter()
    for g in mega.get("_gene_ids", []):
        total_deg[g] = out_deg[g] + in_deg[g]
    top_hubs = total_deg.most_common(15)

    # --- Layout ---
    fig, ax = plt.subplots(1, 1, figsize=(20, 14))
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.0, 1.1)
    ax.set_aspect("equal")
    ax.axis("off")

    # Title
    ax.text(0, 1.08, "Arabidopsis Feedback Architecture", fontsize=18,
            fontweight="bold", ha="center", va="top", fontfamily="sans-serif")
    ax.text(0, 1.03, f"{len(cores)} cores · {sum(c['node_count'] for c in cores)} genes · "
            f"{sum(c['edge_count'] for c in cores)} edges · "
            f"{len(macros)} macro-circuit",
            fontsize=10, ha="center", va="top", color="#64748b", fontfamily="sans-serif")

    # --- Mega-core in center ---
    import math
    mega_x, mega_y = 0.0, 0.15
    mega_r = 0.38

    mega_circle = plt.Circle((mega_x, mega_y), mega_r, fill=True,
                              facecolor="#dbeafe", edgecolor="#2563eb",
                              linewidth=2.5, alpha=0.4, zorder=1)
    ax.add_patch(mega_circle)
    ax.text(mega_x, mega_y + mega_r + 0.03,
            f"Mega-core ({mega['node_count']} genes, {mega['edge_count']} edges)",
            fontsize=11, fontweight="bold", ha="center", va="bottom",
            color="#1e40af", fontfamily="sans-serif")

    # Place top hub genes inside mega-core in a ring
    hub_positions = {}
    n_hubs = len(top_hubs)
    for i, (gene_id, deg) in enumerate(top_hubs):
        angle = 2 * math.pi * i / n_hubs - math.pi / 2
        r = mega_r * 0.68
        hx = mega_x + r * math.cos(angle)
        hy = mega_y + r * math.sin(angle)
        hub_positions[gene_id] = (hx, hy)
        sym = syms.get(gene_id, gene_id)
        fontsize = 7.5 + min(deg / 10, 2)
        ax.plot(hx, hy, "o", color=COLORS["measured"], markersize=4 + deg * 0.3,
                zorder=5, alpha=0.7)
        ax.text(hx, hy + 0.025, sym, fontsize=fontsize, ha="center", va="bottom",
                fontweight="bold" if deg > 20 else "normal", color="#1e3a5f",
                fontfamily="sans-serif", zorder=6)

    # --- Satellites around the mega-core ---
    sat_positions = {}
    n_sats = len(satellites)
    for i, sat in enumerate(satellites):
        angle = 2 * math.pi * i / n_sats - math.pi / 2
        sx = mega_x + (mega_r + 0.22) * math.cos(angle)
        sy = mega_y + (mega_r + 0.22) * math.sin(angle)
        gids = sat.get("_gene_ids", [])
        sym_list = [syms.get(g, g) for g in gids]
        label = " / ".join(sym_list)
        sat_positions[sat["core_id"]] = (sx, sy)

        box_color = "#fef3c7" if sat["node_count"] == 1 else "#e0e7ff"
        edge_color = "#d97706" if sat["node_count"] == 1 else "#6366f1"
        ax.add_patch(mpatches.FancyBboxPatch(
            (sx - 0.07, sy - 0.025), 0.14, 0.05, boxstyle="round,pad=0.01",
            facecolor=box_color, edgecolor=edge_color, linewidth=1.5, zorder=4))
        ax.text(sx, sy, label, fontsize=7, ha="center", va="center",
                fontweight="bold", color="#1f2937", fontfamily="sans-serif", zorder=5)

    # --- Inter-core relationship edges ---
    mega_core_id = mega["core_id"]
    for rel in rels:
        src_cid = rel["source_core_id"]
        tgt_cid = rel["target_core_id"]
        rtype = rel["relationship_type"]

        if src_cid == mega_core_id:
            sx, sy = mega_x, mega_y
        elif src_cid in sat_positions:
            sx, sy = sat_positions[src_cid]
        else:
            continue

        if tgt_cid == mega_core_id:
            tx, ty = mega_x, mega_y
        elif tgt_cid in sat_positions:
            tx, ty = sat_positions[tgt_cid]
        else:
            continue

        ls = "--" if rtype == "bridged_regulatory_path" else "-"
        color = "#6366f1" if rtype == "bridged_regulatory_path" else "#94a3b8"
        ax.annotate("", xy=(tx, ty), xytext=(sx, sy),
                     arrowprops=dict(arrowstyle="->", color=color,
                                     lw=1.0, linestyle=ls, alpha=0.4),
                     zorder=2)

    # --- Macro feedback circuit (the star feature) ---
    if macros:
        macro = macros[0]
        m_genes = macro.get("genes", [])
        m_edges = macro.get("edges", [])

        n_mg = len(m_genes)
        macro_pos = {}
        macro_cx, macro_cy = 0.0, -0.65
        macro_rx, macro_ry = 0.55, 0.22

        for i, g in enumerate(m_genes):
            angle = math.pi + 2 * math.pi * i / n_mg
            mx = macro_cx + macro_rx * math.cos(angle)
            my = macro_cy + macro_ry * math.sin(angle)
            gid = g["id"]
            macro_pos[gid] = (mx, my)

        # Background for macro circuit
        macro_bg = mpatches.FancyBboxPatch(
            (macro_cx - macro_rx - 0.1, macro_cy - macro_ry - 0.08),
            2 * (macro_rx + 0.1), 2 * (macro_ry + 0.08),
            boxstyle="round,pad=0.03", facecolor="#fef9c3", edgecolor="#ca8a04",
            linewidth=2, alpha=0.5, zorder=1)
        ax.add_patch(macro_bg)
        ax.text(macro_cx, macro_cy + macro_ry + 0.10,
                f"Macro-circuit: {macro['architecture'].replace('_', ' ')}",
                fontsize=10, fontweight="bold", ha="center", va="bottom",
                color="#92400e", fontfamily="sans-serif")
        ax.text(macro_cx, macro_cy + macro_ry + 0.06,
                f"{macro['behavior_hypothesis']}",
                fontsize=8, ha="center", va="bottom", color="#a16207",
                fontfamily="sans-serif", style="italic")

        # Draw macro circuit edges
        for e in m_edges:
            src = e.get("source", e.get("source_id"))
            tgt = e.get("target", e.get("target_id"))
            if src not in macro_pos or tgt not in macro_pos:
                continue
            sx, sy = macro_pos[src]
            tx, ty = macro_pos[tgt]
            evidence = e.get("sign_evidence", "unknown")
            sign = e.get("sign", "activation")
            color = EDGE_COLORS.get(evidence, "#94a3b8")
            lw = 2.5 if evidence == "measured" else 2.0
            style = "-" if evidence != "candidate" else "--"
            head = "-|>" if sign == "activation" else "-["
            ax.annotate("", xy=(tx, ty), xytext=(sx, sy),
                         arrowprops=dict(arrowstyle=head, color=color,
                                         lw=lw, linestyle=style,
                                         shrinkA=8, shrinkB=8,
                                         mutation_scale=12),
                         zorder=8)

        # Draw macro circuit gene nodes
        for g in m_genes:
            gid = g["id"]
            mx, my = macro_pos[gid]
            sym = g.get("symbol", gid)
            ax.plot(mx, my, "o", color="white", markersize=12, zorder=9,
                    markeredgecolor="#1f2937", markeredgewidth=1.5)
            ax.text(mx, my - 0.045, sym, fontsize=7.5, ha="center", va="top",
                    fontweight="bold", color="#1f2937", fontfamily="sans-serif",
                    zorder=10)

        # Connect macro circuit to mega-core
        ax.annotate("", xy=(macro_cx, macro_cy + macro_ry + 0.08),
                     xytext=(mega_x, mega_y - mega_r),
                     arrowprops=dict(arrowstyle="<->", color="#ca8a04",
                                     lw=2, linestyle=":", alpha=0.6,
                                     connectionstyle="arc3,rad=0.1"),
                     zorder=3)

    # --- Legend ---
    legend_items = [
        mpatches.Patch(facecolor="#dbeafe", edgecolor="#2563eb", label="Mega-core (measured+perturbation)"),
        mpatches.Patch(facecolor="#e0e7ff", edgecolor="#6366f1", label="Satellite pair core"),
        mpatches.Patch(facecolor="#fef3c7", edgecolor="#d97706", label="Satellite autoregulatory"),
        mpatches.Patch(facecolor="#fef9c3", edgecolor="#ca8a04", label="Macro feedback circuit"),
        plt.Line2D([0], [0], color=EDGE_COLORS["measured"], lw=2.5, label="Measured edge"),
        plt.Line2D([0], [0], color=EDGE_COLORS["perturbation"], lw=2, label="Perturbation edge"),
        plt.Line2D([0], [0], color=EDGE_COLORS["candidate"], lw=2, linestyle="--", label="Candidate edge (cross-species)"),
    ]
    ax.legend(handles=legend_items, loc="lower left", fontsize=8,
              framealpha=0.9, edgecolor="#e2e8f0")

    # Evidence tier annotation
    ax.text(1.08, -0.95,
            "Evidence tiers: measured (curated) · perturbation (KnockTF/ConnecTF)\n"
            "candidate (cross-species transfer via orthology)",
            fontsize=7, ha="right", va="bottom", color="#94a3b8",
            fontfamily="sans-serif", style="italic")

    plt.tight_layout()
    out = Path(__file__).resolve().parent.parent / "arabidopsis_exploratory_feedback.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"Saved: {out}")
    plt.close()
    db.close()


if __name__ == "__main__":
    run()
