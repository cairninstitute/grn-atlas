#!/usr/bin/env python3
"""Arabidopsis mega-core feedback diagram — transit-map style, dark background.

Circuit genes pinned in a tight central cluster. Non-circuit genes in
compact program-grouped clusters around the core. No force-directed layout.
"""

from __future__ import annotations

import math
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from feedback_control import analyze_feedback, FeedbackParameters

BG_COLOR = "#0f172a"
TEXT_COLOR = "#e2e8f0"
SUBTLE_COLOR = "#64748b"

PROGRAMS = {
    "Clock":     "#22d3ee",
    "Floral":    "#f472b6",
    "Meristem":  "#c084fc",
    "Hormone":   "#fb923c",
    "Epidermis": "#a78bfa",
    "Polarity":  "#a3e635",
    "Defense":   "#ef4444",
    "Root":      "#d4a0a0",
    "Cold":      "#3b82f6",
    "Seed":      "#fbbf24",
    "Boundary":  "#2dd4bf",
    "Vascular":  "#8b5cf6",
    "Other":     "#94a3b8",
}

CIRCUIT_COLORS = [
    "#3b82f6", "#f97316", "#22c55e", "#f43f5e", "#a855f7", "#eab308",
    "#06b6d4", "#ec4899", "#14b8a6", "#8b5cf6", "#84cc16", "#ef4444",
]

GENE_PROGRAMS = {
    "LHY": "Clock", "CCA1": "Clock", "PCL1": "Clock", "RVE2": "Clock",
    "COL9": "Clock", "CO": "Clock", "COL5": "Clock", "BOA": "Clock",
    "CDF1": "Clock", "FBH3": "Clock", "FBH4": "Clock", "PIF3": "Clock",
    "PIF7": "Clock", "PIL5": "Clock", "HY5": "Clock", "HYH": "Clock",
    "LZF1": "Clock",
    "LFY": "Floral", "AG": "Floral", "AP1": "Floral", "AP2": "Floral",
    "AP3": "Floral", "PI": "Floral", "SEP3": "Floral", "CAL": "Floral",
    "SVP": "Floral", "AGL20": "Floral", "AGL24": "Floral", "AGL8": "Floral",
    "AGL12": "Floral", "AGL15": "Floral", "AGL17": "Floral", "AGL31": "Floral",
    "FD": "Floral", "FLC": "Floral", "STK": "Floral", "SPL": "Floral",
    "SPL9": "Floral", "SUP": "Floral", "KNU": "Floral", "CRC": "Floral",
    "INO": "Floral", "NAP": "Floral", "RBE": "Floral", "ANT": "Floral",
    "AIL6": "Floral", "BBM": "Floral", "SAP": "Floral", "PAN": "Floral",
    "NAM": "Floral", "VRN1": "Floral",
    "STM": "Meristem", "WUS": "Meristem", "KNAT2": "Meristem",
    "KNAT7": "Meristem", "RPL": "Meristem", "ATH1": "Meristem",
    "JLO": "Meristem", "AS2": "Meristem", "AS1": "Meristem",
    "CUC1": "Meristem", "CUC2": "Meristem", "CUC3": "Meristem",
    "LAS": "Meristem", "SPCH": "Meristem", "ESR1": "Meristem",
    "ABI3": "Hormone", "ABI4": "Hormone", "ABI5": "Hormone",
    "ABF1": "Hormone", "ABF3": "Hormone", "GAI": "Hormone",
    "RGA1": "Hormone", "RGL2": "Hormone", "BES1": "Hormone",
    "ARF2": "Hormone", "ETT": "Hormone", "MYC2": "Hormone",
    "RAV1": "Hormone", "EBP": "Hormone", "DREB2A": "Hormone",
    "BZIP17": "Hormone", "TGA1": "Hormone", "TGA4": "Hormone",
    "bZIP1": "Hormone", "GBF2": "Hormone", "GBF3": "Hormone",
    "CRF2": "Hormone", "MP": "Hormone",
    "GL2": "Epidermis", "GL3": "Epidermis", "EGL3": "Epidermis",
    "TT8": "Epidermis", "TT2": "Epidermis", "TTG2": "Epidermis",
    "CPC": "Epidermis", "ETC1": "Epidermis", "TRY": "Epidermis",
    "TCL1": "Epidermis", "MYB0": "Epidermis", "MYB23": "Epidermis",
    "MYB66": "Epidermis", "MYB5": "Epidermis", "PAP1": "Epidermis",
    "MYB90": "Epidermis", "MYBL2": "Epidermis", "GIS": "Epidermis",
    "ZFP4": "Epidermis",
    "REV": "Polarity", "PHB": "Polarity", "KAN": "Polarity",
    "YAB3": "Polarity", "AFO": "Polarity", "ATS": "Polarity",
    "ATHB-15": "Polarity", "HB-7": "Polarity", "HAT22": "Polarity",
    "PRS": "Polarity", "PTL": "Polarity", "HB51": "Polarity",
    "WRKY11": "Defense", "WRKY17": "Defense", "WRKY18": "Defense",
    "WRKY25": "Defense", "WRKY26": "Defense", "WRKY27": "Defense",
    "WRKY40": "Defense", "WRKY54": "Defense", "WRKY75": "Defense",
    "WRKY2": "Defense", "SR1": "Defense", "HSFB2A": "Defense",
    "RHL41": "Defense",
    "CBF2": "Cold", "ICE1": "Cold",
    "LEC1": "Seed", "LEC2": "Seed", "FUS3": "Seed", "WRI1": "Seed",
    "LBD15": "Boundary", "LBD18": "Boundary", "LBD37": "Boundary",
    "LBD38": "Boundary", "LBD39": "Boundary", "ASL1": "Boundary",
    "VND7": "Vascular", "NST1": "Vascular", "MYB46": "Vascular",
    "MYB83": "Vascular", "NAC066": "Vascular", "NAC042": "Vascular",
    "NAC080": "Vascular",
    "MYB61": "Other", "MYB30": "Other", "MYB3": "Other", "MYB15": "Other",
    "MYB37": "Other", "MYBR1": "Other", "GTL1": "Other", "RAX2": "Other",
    "GATA17": "Other", "BPC1": "Other", "ZAT6": "Other", "TCP11": "Other",
}


def _program(sym):
    return GENE_PROGRAMS.get(sym, "Other")


def _organic_cluster(gids, cx, cy, spacing=0.032, seed=42):
    """Place genes in an organic scattered cluster centered at (cx, cy)."""
    rng = np.random.RandomState(seed)
    n = len(gids)
    positions = {}
    golden_angle = math.pi * (3 - math.sqrt(5))
    for i, gid in enumerate(gids):
        # Fermat spiral with jitter for organic feel
        r = spacing * 0.8 * math.sqrt(i + 0.5)
        theta = i * golden_angle
        jx = rng.uniform(-spacing * 0.25, spacing * 0.25)
        jy = rng.uniform(-spacing * 0.25, spacing * 0.25)
        x = cx + r * math.cos(theta) + jx
        y = cy + r * math.sin(theta) + jy
        positions[gid] = (x, y)
    return positions


def run():
    db = sqlite3.connect(str(BACKEND / "data" / "grn.sqlite3"))
    db.execute("PRAGMA foreign_keys = ON")
    params = FeedbackParameters(include_candidates=True, include_exploratory=True)
    result = analyze_feedback(db, "arabidopsis", params)

    mega = result["cores"][0]
    satellites = result["cores"][1:]
    rels = result.get("core_relationships", [])
    macros = result.get("macro_circuits", [])
    gene_ids = mega["_gene_ids"]
    edges = mega["_backbone_edges"]
    circuits = mega["circuits"]

    syms = {}
    for i in range(0, len(gene_ids), 500):
        batch = gene_ids[i:i + 500]
        for r in db.execute(
            f"SELECT id, symbol FROM genes WHERE id IN ({','.join('?' for _ in batch)})", batch,
        ):
            syms[r[0]] = r[1]
    for sat in satellites:
        for gid in sat.get("_gene_ids", []):
            if gid not in syms:
                r = db.execute("SELECT symbol FROM genes WHERE id=?", (gid,)).fetchone()
                if r:
                    syms[gid] = r[0]

    out_deg, in_deg = Counter(), Counter()
    for e in edges:
        out_deg[e["source"]] += 1
        in_deg[e["target"]] += 1
    total_deg = {g: out_deg[g] + in_deg[g] for g in gene_ids}
    max_deg = max(total_deg.values()) if total_deg else 1

    gene_circuit_membership = defaultdict(set)
    for ci, c in enumerate(circuits):
        for e in c.get("edges", []):
            for g in (e.get("source"), e.get("target")):
                if g:
                    gene_circuit_membership[g].add(ci)
    circuit_gene_set = set(gene_circuit_membership.keys())

    # === LAYOUT ===
    positions = {}

    # --- Circuit genes: hand-placed tight cluster ---
    # LFY at center, floral circuit genes around it, clock pair nearby
    # All within a ~0.12 radius
    cx, cy = 0.42, 0.46
    circuit_pos = {
        # Floral identity core
        "AT5G61850": (cx, cy),                         # LFY — center
        "AT1G69120": (cx + 0.055, cy + 0.015),         # AP1 — right
        "AT3G54340": (cx + 0.055, cy - 0.035),         # AP3 — below-right
        "AT2G22540": (cx + 0.11, cy + 0.030),          # SVP — far right
        "AT2G45660": (cx + 0.085, cy - 0.015),         # AGL20 — right
        "AT5G60910": (cx + 0.075, cy + 0.055),         # AGL8 — above-right
        "AT1G52880": (cx - 0.055, cy + 0.015),         # NAM — left
        "AT1G26310": (cx - 0.035, cy - 0.040),         # CAL — below-left
        "AT5G03790": (cx - 0.075, cy - 0.020),         # HB51 — far left
        # Clock oscillator — above
        "AT1G01060": (cx - 0.10, cy + 0.10),           # LHY — upper-left
        "AT3G46640": (cx - 0.045, cy + 0.10),          # PCL1 — above
        # Hormone autoregulatory
        "AT2G36270": (cx - 0.10, cy - 0.06),           # ABI5 — lower-left
    }
    for gid, pos in circuit_pos.items():
        positions[gid] = pos

    # --- Non-circuit genes: group by program, place in grid clusters ---
    program_groups = defaultdict(list)
    for gid in gene_ids:
        if gid not in circuit_gene_set:
            sym = syms.get(gid, gid)
            prog = _program(sym)
            program_groups[prog].append(gid)

    # Sort each group by degree (highest first)
    for prog in program_groups:
        program_groups[prog].sort(key=lambda g: -total_deg.get(g, 0))

    # Cluster placement (center_x, center_y, columns)
    # Arranged around the circuit core like a map
    cluster_layout = {
        "Floral":    (cx + 0.22, cy - 0.08, 4),   # right, below circuit
        "Clock":     (cx - 0.06, cy + 0.22, 4),   # above
        "Hormone":   (cx - 0.22, cy - 0.04, 4),   # left
        "Meristem":  (cx + 0.18, cy + 0.16, 3),   # upper-right
        "Epidermis": (cx - 0.04, cy - 0.22, 4),   # below
        "Polarity":  (cx + 0.10, cy + 0.20, 3),   # above-right (near HB51)
        "Defense":   (cx - 0.24, cy + 0.14, 3),   # upper-left
        "Seed":      (cx - 0.20, cy - 0.16, 2),   # lower-left
        "Cold":      (cx - 0.24, cy + 0.24, 2),   # far upper-left
        "Boundary":  (cx + 0.24, cy + 0.08, 2),   # right
        "Vascular":  (cx + 0.06, cy + 0.26, 3),   # far above
        "Other":     (cx + 0.24, cy - 0.20, 3),   # lower-right
    }

    for prog, gids in program_groups.items():
        if not gids:
            continue
        pcx, pcy, cols = cluster_layout.get(prog, (cx + 0.3, cy, 3))
        cluster = _organic_cluster(gids, pcx, pcy, spacing=0.045, seed=42 + hash(prog) % 100)
        positions.update(cluster)

    # === Edge classification ===
    edge_circuit = {}
    for ci, circ in enumerate(circuits):
        for e in circ.get("edges", []):
            key = (e.get("source"), e.get("target"))
            edge_circuit.setdefault(key, []).append(ci)

    # === FIGURE ===
    fig = plt.figure(figsize=(30, 21), facecolor=BG_COLOR)
    ax = fig.add_axes([0.01, 0.02, 0.73, 0.95])
    ax.set_facecolor(BG_COLOR)
    ax.axis("off")

    # Set limits with some padding
    all_x = [positions[g][0] for g in gene_ids if g in positions]
    all_y = [positions[g][1] for g in gene_ids if g in positions]
    pad = 0.04
    ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
    ax.set_ylim(min(all_y) - pad, max(all_y) + pad)

    # --- Backbone edges (colored by source gene program) ---
    for e in edges:
        src, tgt = e["source"], e["target"]
        if src == tgt or src not in positions or tgt not in positions:
            continue
        if (src, tgt) in edge_circuit:
            continue
        sx, sy = positions[src]
        tx, ty = positions[tgt]
        tier = e.get("sign_evidence", "unknown")

        src_sym = syms.get(src, src)
        prog = _program(src_sym)
        color = PROGRAMS.get(prog, "#94a3b8")

        if tier == "measured":
            ls, alpha, lw = "-", 0.40, 1.5
        elif tier == "perturbation":
            ls, alpha, lw = (0, (6, 3)), 0.35, 1.3
        elif tier == "candidate":
            ls, alpha, lw = (0, (3, 3)), 0.30, 1.2
        else:
            ls, alpha, lw = (0, (2, 3)), 0.25, 1.0

        ax.plot([sx, tx], [sy, ty], color=color, lw=lw, ls=ls,
                alpha=alpha, zorder=1)

    # --- Circuit lines (bold transit routes) ---
    for ci, circuit in enumerate(circuits):
        color = CIRCUIT_COLORS[ci % len(CIRCUIT_COLORS)]
        for e in circuit.get("edges", []):
            src, tgt = e.get("source"), e.get("target")
            if src not in positions or tgt not in positions:
                continue
            sign = e.get("sign", "activation")

            if src == tgt:
                sx, sy = positions[src]
                r = 0.007
                loop = mpatches.Arc(
                    (sx, sy + r * 1.5), r * 2.0, r * 2.0,
                    angle=0, theta1=30, theta2=330,
                    color=color, lw=1.5, zorder=10,
                )
                ax.add_patch(loop)
                continue

            sx, sy = positions[src]
            tx, ty = positions[tgt]
            dx, dy = tx - sx, ty - sy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.001:
                continue

            # Parallel offset
            nx, ny = -dy / dist, dx / dist
            parallels = edge_circuit.get((src, tgt), [])
            n_par = len(parallels)
            my_idx = parallels.index(ci) if ci in parallels else 0
            offset = (my_idx - (n_par - 1) / 2) * 0.0035
            osx = sx + nx * offset
            osy = sy + ny * offset
            otx = tx + nx * offset
            oty = ty + ny * offset

            ls = "-" if sign == "activation" else (0, (6, 3))
            ax.plot([osx, otx], [osy, oty], color=color, lw=2.0, ls=ls,
                    alpha=0.80, zorder=9, solid_capstyle="round")

            # Arrowhead
            adist = math.sqrt((otx - osx) ** 2 + (oty - osy) ** 2)
            if adist > 0.008:
                arrow = "-|>" if sign == "activation" else "-["
                shrink = 0.006
                mx = otx - (otx - osx) / adist * shrink
                my_ = oty - (oty - osy) / adist * shrink
                ax.annotate("", xy=(otx, oty), xytext=(mx, my_),
                             arrowprops=dict(arrowstyle=arrow, color=color,
                                             lw=1.5, mutation_scale=10),
                             zorder=10)

    # --- Gene nodes ---
    for gid in gene_ids:
        if gid not in positions:
            continue
        sx, sy = positions[gid]
        sym = syms.get(gid, gid)
        prog = _program(sym)
        color = PROGRAMS.get(prog, PROGRAMS["Other"])
        deg = total_deg.get(gid, 0)
        n_circ = len(gene_circuit_membership.get(gid, set()))

        ms = 11 + (deg / max_deg) * 14
        if n_circ > 0:
            ms = max(ms, 16)

        # White ring for junctions
        if n_circ >= 2:
            ax.plot(sx, sy, "o", color="white", markersize=ms + 5,
                    zorder=14, alpha=0.9)

        ax.plot(sx, sy, "o", color=color, markersize=ms,
                markeredgecolor="white" if n_circ >= 2 else "#1e293b",
                markeredgewidth=1.8 if n_circ >= 2 else 0.5,
                zorder=15, alpha=0.95)

        # Circuit membership colored squares below node
        if n_circ > 0:
            sq_w = n_circ * 0.0035
            for ki, cii in enumerate(sorted(gene_circuit_membership[gid])):
                sq_x = sx - sq_w / 2 + ki * 0.0035
                ax.plot(sq_x, sy - ms * 0.00045 - 0.005, "s",
                        color=CIRCUIT_COLORS[cii % len(CIRCUIT_COLORS)],
                        markersize=3.5, zorder=16)

        # Label
        fs = 6.5
        if n_circ > 0:
            fs = 9.5
        elif deg >= 15:
            fs = 8.5
        elif deg >= 8:
            fs = 7.5
        elif deg < 3:
            fs = 5.5
        fw = "bold" if n_circ > 0 or deg >= 15 else "normal"

        ax.text(sx, sy + ms * 0.00045 + 0.004, sym,
                fontsize=fs, ha="center", va="bottom",
                fontweight=fw, color=TEXT_COLOR,
                fontfamily="sans-serif", zorder=17)

    # --- Program cluster labels ---
    for prog, gids in program_groups.items():
        if len(gids) < 2:
            continue
        xs_p = [positions[g][0] for g in gids if g in positions]
        ys_p = [positions[g][1] for g in gids if g in positions]
        if xs_p:
            lx = sum(xs_p) / len(xs_p)
            ly = max(ys_p) + 0.018
            ax.text(lx, ly, prog.upper(), fontsize=7.5, ha="center", va="bottom",
                    color=PROGRAMS.get(prog, "#94a3b8"), alpha=0.5,
                    fontfamily="sans-serif", fontweight="bold", zorder=2)

    # === TITLE ===
    ax.text(0.5, 0.99, "Arabidopsis: Complete Feedback Control Architecture",
            fontsize=20, fontweight="bold", ha="center", va="top",
            color=TEXT_COLOR, fontfamily="sans-serif", transform=ax.transAxes)
    total_cycles = mega.get("cycle_cover", {}).get("circuits_total", "?")
    ax.text(0.5, 0.965,
            f"{len(result['cores'])} feedback cores  |  {len(rels)} inter-core bridges  |  "
            f"{sum(c['node_count'] for c in result['cores'])} genes  |  "
            f"{len(circuits)} of {total_cycles} mega-core circuits shown",
            fontsize=9, ha="center", va="top", color="#22d3ee",
            fontfamily="sans-serif", transform=ax.transAxes)
    ax.text(0.5, 0.945,
            f"CENTRAL HUB — {mega['node_count']} genes · {mega['edge_count']} edges · "
            f"{len(circuits)} circuits",
            fontsize=8, ha="center", va="top", color="#fbbf24",
            fontfamily="sans-serif", transform=ax.transAxes)

    ax.text(0.5, 0.008,
            "Darwin  |  CAIRN Institute GRN Atlas  |  Feedback control v5  |  "
            "Evidence: ATRM, PlantRegMap, ConnecTF, KnockTF, cross-species transfer",
            fontsize=7, ha="center", va="bottom", color=SUBTLE_COLOR,
            fontfamily="sans-serif", transform=ax.transAxes)

    # === RIGHT PANEL ===
    rax = fig.add_axes([0.75, 0.02, 0.24, 0.95])
    rax.set_xlim(0, 1)
    rax.set_ylim(0, 1)
    rax.set_facecolor(BG_COLOR)
    rax.axis("off")

    py = 0.97
    rax.text(0.05, py, "MEGA-CORE CIRCUITS", fontsize=14,
             fontweight="bold", color=TEXT_COLOR, fontfamily="sans-serif")
    py -= 0.018
    rax.text(0.05, py,
             f"{len(circuits)} of {total_cycles} internal feedback loops shown",
             fontsize=7, color=SUBTLE_COLOR, fontfamily="sans-serif")

    def _circuit_function(gene_syms_in_circuit, family):
        """Derive a functional label from the genes in a circuit."""
        gs = set(gene_syms_in_circuit)
        # Exact matches first (1-2 gene circuits)
        if gs == {"ABI5"}:
            return "ABA stress memory"
        if gs == {"PCL1"}:
            return "Clock period control"
        if gs == {"AP1"}:
            return "Floral identity lock-in"
        if gs == {"AP3"}:
            return "Petal identity lock-in"
        if gs == {"AP1", "LFY"}:
            return "Floral meristem identity"
        if gs == {"NAM", "LFY"}:
            return "Floral–boundary coordination"
        if gs == {"LHY", "PCL1"}:
            return "Clock oscillation"
        # 3-gene circuits
        if gs <= {"LFY", "HB51", "HBS1", "CAL"} and len(gs) == 3:
            return "Floral commitment amplifier"
        if gs == {"LFY", "AP3", "AP1"}:
            return "Petal–sepal crosstalk"
        if gs == {"LFY", "AP1", "AGL8"}:
            return "Fruit development switch"
        if gs == {"LFY", "AP1", "AGL20"}:
            return "Floral repression balance"
        # 4-gene circuits
        if gs == {"LFY", "AP1", "SVP", "AGL20"}:
            return "Vernalization–floral timing"
        # 5-gene circuits
        if gs == {"LFY", "AP3", "AP1", "SVP", "AGL20"}:
            return "Floral organ patterning"
        return family.replace("_", " ").title()

    for ci, circuit in enumerate(circuits):
        py -= 0.032
        col = CIRCUIT_COLORS[ci % len(CIRCUIT_COLORS)]
        family = circuit["family"]

        c_edges = circuit.get("edges", [])
        parts = []
        circuit_gene_syms = []
        for e in c_edges:
            ss = syms.get(e["source"], e["source"])
            ts = syms.get(e["target"], e["target"])
            sign = "→" if e["sign"] == "activation" else "⊣"
            if not parts:
                parts.append(ss)
                circuit_gene_syms.append(ss)
            parts.append(f"{sign} {ts}")
            if ts not in circuit_gene_syms:
                circuit_gene_syms.append(ts)
        chain = " ".join(parts)
        func_label = _circuit_function(circuit_gene_syms, family)

        rax.plot([0.05, 0.11], [py + 0.005, py + 0.005], color=col, lw=4,
                 solid_capstyle="round")
        rax.text(0.13, py + 0.005, func_label,
                 fontsize=8.5, va="center", color=TEXT_COLOR,
                 fontfamily="sans-serif", fontweight="bold")
        rax.text(0.13, py - 0.010, chain[:55],
                 fontsize=6, va="center", color=col, fontfamily="sans-serif",
                 alpha=0.8)

    # Satellites
    py -= 0.045
    rax.text(0.05, py, f"SATELLITE CORES ({len(satellites)})", fontsize=14,
             fontweight="bold", color=TEXT_COLOR, fontfamily="sans-serif")

    sat_info = {
        "FEZ / SMB": ("[-]", "Root cap cell fate"),
        "SCR / JKD": ("[+]", "Ground tissue identity"),
        "HFR1 / HB-2": ("[-]", "Light response"),
        "ABI4": ("[+]", "Upstream — ABA signaling"),
        "MP": ("[+]", "Upstream — auxin response"),
        "KNAT1": ("[+]", "Meristem self-activation"),
        "WRKY29": ("[+]", "Defense reinforcement"),
        "WRKY53": ("[+]", "Senescence damping"),
        "WRKY6": ("[+]", "Defense damping"),
        "MYB4": ("[-]", "Phenylpropanoid damping"),
        "RAP2.1": ("[-]", "Cold response damping"),
    }
    for si, sat in enumerate(satellites):
        py -= 0.022
        gids = sat.get("_gene_ids", [])
        label = " / ".join(syms.get(g, g) for g in gids)
        pol, desc = sat_info.get(label, ("[?]", ""))
        pol_c = "#22c55e" if "+" in pol else "#ef4444"
        rax.text(0.05, py, pol, fontsize=7.5, va="center", color=pol_c,
                 fontfamily="sans-serif", fontweight="bold")
        rax.text(0.12, py, label, fontsize=8, va="center", color=TEXT_COLOR,
                 fontfamily="sans-serif", fontweight="bold")
        rax.text(0.42, py, desc, fontsize=7, va="center", color=SUBTLE_COLOR,
                 fontfamily="sans-serif")

    # Gene programs
    py -= 0.04
    rax.text(0.05, py, "GENE PROGRAMS", fontsize=14,
             fontweight="bold", color=TEXT_COLOR, fontfamily="sans-serif")
    for pi, (prog, col) in enumerate(PROGRAMS.items()):
        c_ = pi % 2
        r_ = pi // 2
        px = 0.05 + c_ * 0.45
        ppy = py - 0.025 - r_ * 0.023
        rax.plot(px, ppy, "o", color=col, markersize=7)
        rax.text(px + 0.03, ppy, prog, fontsize=8, va="center",
                 color=TEXT_COLOR, fontfamily="sans-serif")

    # How to read
    py = py - 0.025 - (len(PROGRAMS) // 2 + 1) * 0.023 - 0.03
    rax.text(0.05, py, "HOW TO READ", fontsize=14,
             fontweight="bold", color=TEXT_COLOR, fontfamily="sans-serif")
    # Explanatory subtitle
    py -= 0.018
    rax.text(0.05, py, "Each line = one TF → target regulatory edge",
             fontsize=7, va="center", color=SUBTLE_COLOR,
             fontfamily="sans-serif", style="italic")
    py -= 0.012
    rax.text(0.05, py, "Line color = source TF gene program",
             fontsize=7, va="center", color=SUBTLE_COLOR,
             fontfamily="sans-serif", style="italic")
    # Draw actual line samples for evidence tiers
    line_items = [
        ("-", 1.5, "#f472b6", 0.40, "Measured binding (ChIP/DAP)"),
        ((0, (6, 3)), 1.3, "#f472b6", 0.35, "Perturbation evidence"),
        ((0, (3, 3)), 1.2, "#f472b6", 0.30, "Cross-species transfer"),
    ]
    for li, (ls, lw, col, alpha, desc) in enumerate(line_items):
        hy = py - 0.025 - li * 0.025
        rax.plot([0.05, 0.18], [hy, hy], color=col, lw=lw, ls=ls,
                 alpha=alpha, solid_capstyle="round")
        rax.text(0.21, hy, desc, fontsize=7.5, va="center", color=TEXT_COLOR,
                 fontfamily="sans-serif")

    # Node/circuit legend items
    node_items = [
        ("Gene node ●", "Color = gene program", None),
        ("Colored circuit line", "Feedback circuit path", "#22c55e"),
        ("White ring", "Junction (2+ circuits)", "#ffffff"),
        ("Colored squares", "Circuit membership", TEXT_COLOR),
    ]
    for ni, (sym, desc, col) in enumerate(node_items):
        hy = py - 0.025 - (len(line_items) + ni) * 0.025
        sym_col = col if col else TEXT_COLOR
        rax.text(0.05, hy, sym, fontsize=7.5, va="center", color=sym_col,
                 fontfamily="sans-serif", fontweight="bold")
        rax.text(0.42, hy, desc, fontsize=7.5, va="center", color=TEXT_COLOR,
                 fontfamily="sans-serif")

    # Macro circuit
    if macros:
        macro = macros[0]
        py = py - 0.025 - (len(line_items) + len(node_items)) * 0.025 - 0.03
        rax.text(0.05, py, "MACRO FEEDBACK CIRCUIT", fontsize=12,
                 fontweight="bold", color="#fbbf24", fontfamily="sans-serif")
        mg = macro.get("genes", [])
        l1 = " → ".join(g.get("symbol", "?") for g in mg[:6])
        l2 = " → ".join(g.get("symbol", "?") for g in mg[6:])
        rax.text(0.05, py - 0.02, l1 + " →",
                 fontsize=7, color="#fbbf24", fontfamily="sans-serif")
        rax.text(0.05, py - 0.038, l2,
                 fontsize=7, color="#fbbf24", fontfamily="sans-serif")
        arch = macro.get("architecture", "").replace("_", " ")
        rax.text(0.05, py - 0.058,
                 f"{arch} — {macro.get('behavior_hypothesis', '')}",
                 fontsize=6.5, color=SUBTLE_COLOR, fontfamily="sans-serif",
                 style="italic")

    out = Path(__file__).resolve().parent.parent / "arabidopsis_megacore_circuits.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG_COLOR)
    print(f"Saved: {out}")
    plt.close()
    db.close()


if __name__ == "__main__":
    run()
