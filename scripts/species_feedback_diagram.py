#!/usr/bin/env python3
"""Generate feedback architecture diagrams for any species.

Auto-layouts genes using Fermat spiral clusters grouped by TF family.
Adapts to species scale: small cores get simple layouts, large ones
use program-grouped clusters around a central hub.

Usage:
    venv/bin/python scripts/species_feedback_diagram.py human
    venv/bin/python scripts/species_feedback_diagram.py --all
"""

from __future__ import annotations

import argparse
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

CIRCUIT_COLORS = [
    "#3b82f6", "#f97316", "#22c55e", "#f43f5e", "#a855f7", "#eab308",
    "#06b6d4", "#ec4899", "#14b8a6", "#8b5cf6", "#84cc16", "#ef4444",
]

TF_FAMILY_COLORS = {
    # Plant families
    "MYB":       "#f472b6",
    "WRKY":      "#ef4444",
    "NAC":       "#fb923c",
    "bHLH":      "#a78bfa",
    "AP2/ERF":   "#22c55e",
    "bZIP":      "#fbbf24",
    "MADS":      "#ec4899",
    "HD-ZIP":    "#a3e635",
    "TCP":       "#06b6d4",
    "C2H2":      "#14b8a6",
    "GRAS":      "#8b5cf6",
    "SBP":       "#22d3ee",
    "Homeobox":  "#c084fc",
    "LOB":       "#2dd4bf",
    "HSF":       "#f97316",
    "Dof":       "#84cc16",
    "GATA":      "#d4a0a0",
    "NF-Y":      "#3b82f6",
    # Animal families
    "FOX":       "#22c55e",
    "SOX":       "#06b6d4",
    "HOX":       "#c084fc",
    "KLF/SP":    "#a3e635",
    "ETS":       "#f97316",
    "STAT":      "#14b8a6",
    "NF-kB":     "#ef4444",
    "p53":       "#ec4899",
    "E2F":       "#8b5cf6",
    "PAX":       "#22d3ee",
    "SMAD":      "#fb923c",
    "IRF":       "#fbbf24",
    "CEBP":      "#a78bfa",
    "RUNX":      "#2dd4bf",
    "Nuclear receptor": "#f472b6",
    "AP-1":      "#84cc16",
    "EGR":       "#d4a0a0",
    "NFAT":      "#3b82f6",
    "HES/HEY":   "#e879f9",
    "Other":     "#94a3b8",
}


def _classify_tf_family(symbol: str) -> str:
    sym = symbol.upper()

    # --- Animal TF families (check first — more specific names) ---
    if sym.startswith("FOX"):
        return "FOX"
    if sym.startswith("SOX"):
        return "SOX"
    if sym.startswith("HOX") or sym.startswith("CDX") or sym.startswith("MEIS") or \
       sym.startswith("PBX"):
        return "HOX"
    if sym.startswith("KLF") or (sym.startswith("SP") and len(sym) <= 3 and sym[-1].isdigit()):
        return "KLF/SP"
    if sym.startswith("ETS") or sym.startswith("ELF") or sym.startswith("ELK") or \
       sym in ("ERG", "FLI1", "FEV", "SPI1", "SPIB", "SPIC", "GABPA", "EHF", "ETV1",
               "ETV4", "ETV5", "ETV6", "ETV7", "ERF"):
        return "ETS"
    if sym.startswith("STAT"):
        return "STAT"
    if sym.startswith("NFKB") or sym in ("RELA", "RELB", "REL", "NFKB1", "NFKB2"):
        return "NF-kB"
    if sym in ("TP53", "TP63", "TP73", "P53", "P63", "P73"):
        return "p53"
    if sym.startswith("E2F") or sym.startswith("TFDP"):
        return "E2F"
    if sym.startswith("PAX"):
        return "PAX"
    if sym.startswith("SMAD"):
        return "SMAD"
    if sym.startswith("IRF"):
        return "IRF"
    if sym.startswith("CEBP") or sym.startswith("C/EBP"):
        return "CEBP"
    if sym.startswith("RUNX") or sym.startswith("CBFB"):
        return "RUNX"
    if sym in ("AR", "ESR1", "ESR2", "PGR", "NR3C1", "NR3C2", "NR1H2", "NR1H3",
               "NR1H4", "NR4A1", "NR4A2", "NR4A3", "VDR", "RARA", "RARB", "RARG",
               "RXRA", "RXRB", "RXRG", "PPARA", "PPARG", "PPARD", "HNF4A", "HNF4G",
               "THRA", "THRB", "NR2F1", "NR2F2", "NR5A1", "NR5A2", "LRH1"):
        return "Nuclear receptor"
    if sym.startswith("JUN") or sym.startswith("FOS") or sym in ("BATF", "BATF3", "ATF3",
               "ATF4", "ATF7", "BACH1", "BACH2", "NFE2L2", "MAFF", "MAFK", "MAFG"):
        return "AP-1"
    if sym.startswith("EGR"):
        return "EGR"
    if sym.startswith("NFAT"):
        return "NFAT"
    if sym.startswith("HES") or sym.startswith("HEY"):
        return "HES/HEY"
    if sym.startswith("GATA"):
        return "GATA"
    if sym.startswith("MYB") or sym.startswith("PAP") or sym.startswith("TT2"):
        return "MYB"
    if sym in ("MYC", "MYCN", "MYCL", "MAX", "MXD1", "MNT", "MGA"):
        return "bHLH"
    if sym in ("NANOG", "POU5F1", "POU2F1", "POU2F2", "POU3F2"):
        return "Homeobox"
    if sym.startswith("TBX") or sym.startswith("EOMES") or sym in ("TBR1", "BRACHYURY", "T"):
        return "Homeobox"
    if sym.startswith("NKX") or sym.startswith("DLX") or sym.startswith("LHX") or \
       sym.startswith("OTX") or sym.startswith("EMX") or sym.startswith("SIX") or \
       sym.startswith("PITX") or sym.startswith("ISL") or sym.startswith("EN"):
        return "Homeobox"
    if sym.startswith("TWIST") or sym.startswith("SNAI") or sym.startswith("ZEB") or \
       sym in ("SLUG",):
        return "bHLH"
    if sym.startswith("TCF") or sym.startswith("LEF"):
        return "Homeobox"
    if sym.startswith("NOTCH") or sym.startswith("RBPJ"):
        return "HES/HEY"
    if sym.startswith("NF1") or sym.startswith("NFI"):
        return "Other"

    # --- Plant TF families ---
    if sym.startswith("WRKY"):
        return "WRKY"
    if sym.startswith("NAC") or sym.startswith("CUC") or sym.startswith("NAM"):
        return "NAC"
    if sym.startswith("PIF") or sym.startswith("PIL") or sym.startswith("ICE") or \
       sym.startswith("MYC") or sym.startswith("BEE") or sym.startswith("TT8") or \
       sym.startswith("GL3") or sym.startswith("EGL"):
        return "bHLH"
    if sym.startswith("ERF") or sym.startswith("DREB") or sym.startswith("RAP2") or \
       sym.startswith("CBF") or sym.startswith("AP2") or sym.startswith("BBM") or \
       sym.startswith("AIL") or sym.startswith("ANT") or sym.startswith("ESR"):
        return "AP2/ERF"
    if sym.startswith("BZIP") or sym.startswith("TGA") or sym.startswith("ABI5") or \
       sym.startswith("ABF") or sym.startswith("HY5") or sym.startswith("GBF") or \
       sym.startswith("FD"):
        return "bZIP"
    if sym.startswith("AGL") or sym.startswith("SVP") or sym.startswith("AP1") or \
       sym.startswith("AP3") or sym.startswith("AG") or sym.startswith("SEP") or \
       sym.startswith("FLC") or sym.startswith("STK") or sym.startswith("CAL") or \
       sym.startswith("PI") or sym.startswith("SOC"):
        return "MADS"
    if sym.startswith("REV") or sym.startswith("PHB") or sym.startswith("ATHB") or \
       sym.startswith("HB") or sym.startswith("HAT") or sym.startswith("HD-ZIP"):
        return "HD-ZIP"
    if sym.startswith("TCP"):
        return "TCP"
    if sym.startswith("ZAT") or sym.startswith("ZFP") or sym.startswith("STZ") or \
       sym.startswith("ZNF"):
        return "C2H2"
    if sym.startswith("GAI") or sym.startswith("RGA") or sym.startswith("RGL") or \
       sym.startswith("SCR") or sym.startswith("SHR") or sym.startswith("LAS"):
        return "GRAS"
    if sym.startswith("SPL"):
        return "SBP"
    if sym.startswith("LBD") or sym.startswith("ASL") or sym.startswith("LOB"):
        return "LOB"
    if sym.startswith("HSF"):
        return "HSF"
    if sym.startswith("DOF") or sym.startswith("CDF"):
        return "Dof"
    if sym.startswith("NF-Y") or sym.startswith("LEC1"):
        return "NF-Y"
    if sym.startswith("KNAT") or sym.startswith("STM") or sym.startswith("WUS") or \
       sym.startswith("KN") or sym.startswith("WOX"):
        return "Homeobox"
    return "Other"


def _organic_cluster(gids, cx, cy, spacing=0.032, seed=42):
    rng = np.random.RandomState(seed)
    positions = {}
    golden_angle = math.pi * (3 - math.sqrt(5))
    for i, gid in enumerate(gids):
        r = spacing * 0.8 * math.sqrt(i + 0.5)
        theta = i * golden_angle
        jx = rng.uniform(-spacing * 0.25, spacing * 0.25)
        jy = rng.uniform(-spacing * 0.25, spacing * 0.25)
        x = cx + r * math.cos(theta) + jx
        y = cy + r * math.sin(theta) + jy
        positions[gid] = (x, y)
    return positions


def _circuit_function(gene_syms: list[str], families: list[str], family: str,
                      species: str = "") -> str:
    """Derive a functional label from circuit gene symbols and TF families."""
    gs = set(gene_syms)
    fams = set(families)
    n = len(gs)
    is_animal = species in ("human", "mouse")

    # Autoregulation (1 gene)
    if n == 1:
        sym = gene_syms[0]
        fam = families[0] if families else "Other"
        if fam == "MADS" and not is_animal:
            return f"{sym} floral identity lock-in"
        if fam == "MYB":
            return f"{sym} MYB autoregulation"
        if fam == "AP2/ERF" and not is_animal:
            return f"{sym} stress/development lock-in"
        if fam == "bZIP":
            return f"{sym} stress memory"
        if not is_animal and ("clock" in family.lower() or
                sym.upper() in ("LHY", "CCA1", "PCL1", "TOC1", "PRR5", "PRR7")):
            return f"{sym} clock control"
        return f"{sym} self-regulation"

    # Mutual activation/feedback (2 genes)
    if n == 2:
        s1, s2 = sorted(gs)
        if is_animal:
            if "MYB" in fams:
                return f"{s1}–{s2} MYB regulation"
            return f"{s1}–{s2} mutual regulation"
        if fams == {"MADS"} or fams <= {"MADS", "Other"}:
            return f"{s1}–{s2} floral identity"
        if "WRKY" in fams:
            return f"{s1}–{s2} defense crosstalk"
        if "MYB" in fams:
            return f"{s1}–{s2} MYB regulation"
        return f"{s1}–{s2} mutual regulation"

    # Larger circuits — classify by dominant family
    fam_counts = Counter(families)
    dominant = fam_counts.most_common(1)[0][0] if fam_counts else "Other"

    # Check for known biological motifs
    sym_upper = {s.upper() for s in gs}
    has_floral = bool(sym_upper & {"AP1", "AP3", "AG", "PI", "SEP3", "AGL9", "CAL", "FUL", "FUL1",
                                    "LFY", "ALF", "SVP", "AGL20", "AGL24", "SOC1", "STK"})
    has_clock = bool(sym_upper & {"LHY", "CCA1", "PCL1", "TOC1", "PRR5", "PRR7", "GI", "CO"})
    has_epidermis = bool(sym_upper & {"GL1", "GL2", "GL3", "CPC", "TRY", "ETC1", "TTG2", "MYB0"})
    has_hormone = bool(sym_upper & {"ABI3", "ABI4", "ABI5", "EBP", "ERF1", "ARF2", "ETT", "MYC2",
                                     "GAI", "RGA1", "BES1"})
    has_meristem = bool(sym_upper & {"STM", "WUS", "KNAT1", "KNAT2", "BP", "AS1", "AS2", "CUC1",
                                      "CUC2", "CUC3"})

    if is_animal:
        # Animal-specific circuit labels
        sym_upper = {s.upper() for s in gs}
        has_tumor_suppressor = bool(sym_upper & {"TP53", "RB1", "PTEN", "BRCA1", "APC", "VHL"})
        has_cell_cycle = bool(sym_upper & {"E2F1", "E2F6", "MYC", "CCND1", "CDK4", "RB1"})
        has_immune = bool(sym_upper & {"NFKB1", "RELA", "IRF1", "STAT1", "STAT3", "TNF"})
        has_stem = bool(sym_upper & {"NANOG", "SOX2", "POU5F1", "KLF4", "MYC"})
        if has_tumor_suppressor and has_cell_cycle:
            return "Cell cycle checkpoint"
        if has_cell_cycle:
            if "negative" in family:
                return "Cell cycle repression"
            return "Cell cycle progression"
        if has_tumor_suppressor:
            return "Tumor suppressor loop"
        if has_immune:
            return "Immune signaling loop"
        if has_stem:
            return "Stemness maintenance"
        if dominant == "Homeobox":
            return "Developmental patterning"
        if "negative" in family:
            return f"{n}-gene repression loop"
        return f"{n}-gene regulatory loop"

    if has_floral and has_clock:
        return "Floral–clock integration"
    if has_floral and has_epidermis:
        return "Floral–epidermal patterning"
    if has_floral and has_meristem:
        return "Floral–meristem transition"
    if has_floral and has_hormone:
        return "Floral–hormone signaling"
    if has_floral:
        if "negative" in family:
            if n <= 3:
                return "Floral repression balance"
            return "Floral organ patterning"
        if "mutual" in family:
            return "Floral identity reinforcement"
        if n <= 3:
            return "Floral commitment"
        return "Floral timing integration"
    if has_clock:
        return "Clock oscillation"
    if has_epidermis:
        return "Epidermal patterning"
    if has_hormone:
        return "Hormone signaling loop"
    if has_meristem:
        return "Meristem maintenance"

    # Fall back to TF family
    if dominant == "MADS":
        return "MADS-box regulatory loop"
    if dominant == "WRKY":
        return "Defense regulatory loop"
    if dominant == "MYB":
        return "MYB regulatory loop"
    if dominant == "NAC":
        return "NAC developmental loop"
    if dominant == "AP2/ERF":
        return "AP2/ERF signaling loop"
    if dominant == "HD-ZIP":
        return "Polarity patterning"
    if dominant == "Homeobox":
        return "Homeobox developmental loop"

    return f"{n}-gene regulatory loop"


def _auto_cluster_centers(families, cx=0.42, cy=0.42, radius=0.25):
    centers = {}
    n = len(families)
    for i, fam in enumerate(sorted(families)):
        angle = 2 * math.pi * i / max(n, 1) - math.pi / 2
        centers[fam] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
    return centers


def generate_diagram(species: str, db: sqlite3.Connection):
    params = FeedbackParameters(include_candidates=True, include_exploratory=True)
    result = analyze_feedback(db, species, params)

    cores = result["cores"]
    if not cores:
        print(f"  {species}: no feedback cores, skipping")
        return

    mega = cores[0]
    satellites = cores[1:]
    rels = result.get("core_relationships", [])
    macros = result.get("macro_circuits", [])
    gene_ids = mega["_gene_ids"]
    edges = mega["_backbone_edges"]
    circuits = mega.get("circuits", [])

    all_gene_ids = list(gene_ids)
    for sat in satellites:
        all_gene_ids.extend(sat.get("_gene_ids", []))

    syms = {}
    for i in range(0, len(all_gene_ids), 500):
        batch = all_gene_ids[i:i + 500]
        for r in db.execute(
            f"SELECT id, symbol FROM genes WHERE id IN ({','.join('?' for _ in batch)})", batch,
        ):
            syms[r[0]] = r[1]

    # Resolve better names from aliases for genes that still have locus IDs
    locus_genes = [g for g in all_gene_ids if syms.get(g, g) == g or
                   syms.get(g, "").startswith("LOC_") or
                   syms.get(g, "").startswith("Solyc") or
                   syms.get(g, "").startswith("Peaxi")]
    for i in range(0, len(locus_genes), 500):
        batch = locus_genes[i:i + 500]
        ph = ",".join("?" for _ in batch)
        aliases = db.execute(
            f"SELECT gene_id, alias FROM gene_aliases WHERE gene_id IN ({ph})", batch
        ).fetchall()
        # Group by gene, pick shortest non-AT alias as display name
        from collections import defaultdict as _dd
        gene_aliases = _dd(list)
        for gid, alias in aliases:
            gene_aliases[gid].append(alias)
        for gid, als in gene_aliases.items():
            # Prefer short common names, skip long descriptions and AT-prefixed names
            candidates = [a for a in als if len(a) <= 12 and not a.startswith("AT")
                          and not a.startswith("ARABIDOPSIS") and not a.lower().startswith("at")]
            if not candidates:
                candidates = [a for a in als if len(a) <= 20 and not a.startswith("ARABIDOPSIS")]
            if candidates:
                syms[gid] = min(candidates, key=len)

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

    # Classify genes by TF family (use resolved common names)
    gene_family = {}
    for gid in gene_ids:
        sym = syms.get(gid, gid)
        gene_family[gid] = _classify_tf_family(sym)
    for gid in all_gene_ids:
        if gid not in gene_family:
            gene_family[gid] = _classify_tf_family(syms.get(gid, gid))

    # === LAYOUT ===
    positions = {}
    cx, cy = 0.42, 0.42

    # Group non-circuit genes by family
    family_groups = defaultdict(list)
    for gid in gene_ids:
        if gid not in circuit_gene_set:
            family_groups[gene_family[gid]].append(gid)

    for fam in family_groups:
        family_groups[fam].sort(key=lambda g: -total_deg.get(g, 0))

    n_genes = len(gene_ids)
    if n_genes <= 20:
        spacing = 0.06
        cluster_radius = 0.20
    elif n_genes <= 50:
        spacing = 0.05
        cluster_radius = 0.25
    elif n_genes <= 150:
        spacing = 0.045
        cluster_radius = 0.28
    else:
        spacing = 0.035
        cluster_radius = 0.32

    # Place circuit genes in center
    if circuit_gene_set:
        circ_list = sorted(circuit_gene_set)
        circ_positions = _organic_cluster(circ_list, cx, cy, spacing=spacing * 0.6, seed=99)
        positions.update(circ_positions)

    # Place family clusters around center
    families_with_genes = [f for f in family_groups if family_groups[f]]
    cluster_centers = _auto_cluster_centers(families_with_genes, cx, cy, cluster_radius)

    for fam, gids in family_groups.items():
        if not gids:
            continue
        fcx, fcy = cluster_centers.get(fam, (cx + 0.3, cy))
        cluster = _organic_cluster(gids, fcx, fcy, spacing=spacing, seed=42 + hash(fam) % 100)
        positions.update(cluster)

    # Edge classification for circuits
    edge_circuit = {}
    for ci, circ in enumerate(circuits):
        for e in circ.get("edges", []):
            key = (e.get("source"), e.get("target"))
            edge_circuit.setdefault(key, []).append(ci)

    # === FIGURE ===
    fig_w = 30 if n_genes > 50 else 22
    fig_h = int(fig_w * 0.72)
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=BG_COLOR)
    ax = fig.add_axes([0.01, 0.02, 0.73, 0.95])
    ax.set_facecolor(BG_COLOR)
    ax.axis("off")

    positioned_genes = [g for g in gene_ids if g in positions]
    if not positioned_genes:
        print(f"  {species}: no genes positioned, skipping")
        plt.close()
        return

    all_x = [positions[g][0] for g in positioned_genes]
    all_y = [positions[g][1] for g in positioned_genes]
    pad = 0.04
    ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
    ax.set_ylim(min(all_y) - pad, max(all_y) + pad)

    # --- Backbone edges ---
    for e in edges:
        src, tgt = e["source"], e["target"]
        if src == tgt or src not in positions or tgt not in positions:
            continue
        if (src, tgt) in edge_circuit:
            continue
        sx, sy = positions[src]
        tx, ty = positions[tgt]
        tier = e.get("sign_evidence", "unknown")

        src_fam = gene_family.get(src, "Other")
        color = TF_FAMILY_COLORS.get(src_fam, "#94a3b8")

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

    # --- Circuit lines ---
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

            adist = math.sqrt((otx - osx) ** 2 + (oty - osy) ** 2)
            if adist > 0.008:
                arrow = "-|>" if sign == "activation" else "-["
                shrink = 0.006
                mx = otx - (otx - osx) / adist * shrink
                my = oty - (oty - osy) / adist * shrink
                ax.annotate("", xy=(otx, oty), xytext=(mx, my),
                            arrowprops=dict(arrowstyle=arrow, color=color,
                                            lw=1.5, mutation_scale=10),
                            zorder=11)

    # --- Gene nodes ---
    for gid in gene_ids:
        if gid not in positions:
            continue
        sx, sy = positions[gid]
        sym = syms.get(gid, gid)
        fam = gene_family.get(gid, "Other")
        color = TF_FAMILY_COLORS.get(fam, "#94a3b8")
        deg = total_deg.get(gid, 0)
        n_circ = len(gene_circuit_membership.get(gid, set()))

        ms = 11 + (deg / max_deg) * 14
        if n_circ > 0:
            ms = max(ms, 16)

        if n_circ >= 2:
            ax.plot(sx, sy, "o", color="white", markersize=ms + 5,
                    zorder=14, alpha=0.9)

        ax.plot(sx, sy, "o", color=color, markersize=ms,
                markeredgecolor="white" if n_circ >= 2 else "#1e293b",
                markeredgewidth=1.8 if n_circ >= 2 else 0.5,
                zorder=15, alpha=0.95)

        if n_circ > 0:
            sq_w = n_circ * 0.0035
            for ki, cii in enumerate(sorted(gene_circuit_membership[gid])):
                sq_x = sx - sq_w / 2 + ki * 0.0035
                ax.plot(sq_x, sy - ms * 0.00045 - 0.005, "s",
                        color=CIRCUIT_COLORS[cii % len(CIRCUIT_COLORS)],
                        markersize=3.5, zorder=16)

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

    # --- Family cluster labels ---
    for fam, gids in family_groups.items():
        if len(gids) < 2:
            continue
        xs_p = [positions[g][0] for g in gids if g in positions]
        ys_p = [positions[g][1] for g in gids if g in positions]
        if xs_p:
            lx = sum(xs_p) / len(xs_p)
            ly = max(ys_p) + 0.018
            ax.text(lx, ly, fam.upper(), fontsize=7.5, ha="center", va="bottom",
                    color=TF_FAMILY_COLORS.get(fam, "#94a3b8"), alpha=0.5,
                    fontfamily="sans-serif", fontweight="bold", zorder=2)

    # === TITLE ===
    species_title = species.replace("_", " ").title()
    ax.text(0.5, 0.99, f"{species_title}: Complete Feedback Control Architecture",
            fontsize=20, fontweight="bold", ha="center", va="top",
            color=TEXT_COLOR, fontfamily="sans-serif", transform=ax.transAxes)
    total_cycles = mega.get("cycle_cover", {}).get("circuits_total", "?")
    ax.text(0.5, 0.965,
            f"{len(cores)} feedback cores  |  {len(rels)} inter-core bridges  |  "
            f"{sum(c['node_count'] for c in cores)} genes  |  "
            f"{len(circuits)} circuits  |  {len(macros)} macro-circuits",
            fontsize=9, ha="center", va="top", color="#22d3ee",
            fontfamily="sans-serif", transform=ax.transAxes)
    ax.text(0.5, 0.945,
            f"CENTRAL HUB — {mega['node_count']} genes · {mega['edge_count']} edges",
            fontsize=8, ha="center", va="top", color="#fbbf24",
            fontfamily="sans-serif", transform=ax.transAxes)

    ax.text(0.5, 0.008,
            "Darwin  |  CAIRN Institute GRN Atlas  |  Feedback control v5  |  "
            "Evidence: curated, perturbation, cross-species transfer",
            fontsize=7, ha="center", va="bottom", color=SUBTLE_COLOR,
            fontfamily="sans-serif", transform=ax.transAxes)

    # === RIGHT PANEL ===
    rax = fig.add_axes([0.75, 0.02, 0.24, 0.95])
    rax.set_xlim(0, 1)
    rax.set_ylim(0, 1)
    rax.set_facecolor(BG_COLOR)
    rax.axis("off")

    py = 0.97

    # Circuits (if any)
    if circuits:
        rax.text(0.05, py, "MEGA-CORE CIRCUITS", fontsize=14,
                 fontweight="bold", color=TEXT_COLOR, fontfamily="sans-serif")
        py -= 0.018
        rax.text(0.05, py, f"{len(circuits)} internal feedback loops",
                 fontsize=7, color=SUBTLE_COLOR, fontfamily="sans-serif")

        for ci, circuit in enumerate(circuits):
            py -= 0.032
            col = CIRCUIT_COLORS[ci % len(CIRCUIT_COLORS)]
            c_edges = circuit.get("edges", [])
            parts = []
            circuit_gene_syms = []
            circuit_gene_fams = []
            for e in c_edges:
                ss = syms.get(e["source"], e["source"])
                ts = syms.get(e["target"], e["target"])
                sign = "→" if e["sign"] == "activation" else "⊣"
                if not parts:
                    parts.append(ss)
                    circuit_gene_syms.append(ss)
                    circuit_gene_fams.append(_classify_tf_family(ss))
                parts.append(f"{sign} {ts}")
                if ts not in circuit_gene_syms:
                    circuit_gene_syms.append(ts)
                    circuit_gene_fams.append(_classify_tf_family(ts))
            chain = " ".join(parts)
            func_label = _circuit_function(circuit_gene_syms, circuit_gene_fams,
                                           circuit.get("family", ""), species)

            rax.plot([0.05, 0.11], [py + 0.005, py + 0.005], color=col, lw=4,
                     solid_capstyle="round")
            rax.text(0.13, py + 0.005, func_label,
                     fontsize=8.5, va="center", color=TEXT_COLOR,
                     fontfamily="sans-serif", fontweight="bold")
            rax.text(0.13, py - 0.010, chain[:55],
                     fontsize=6, va="center", color=col, fontfamily="sans-serif",
                     alpha=0.8)
        py -= 0.02

    # Macro-circuits
    if macros:
        py -= 0.02
        rax.text(0.05, py, f"MACRO FEEDBACK CIRCUITS ({len(macros)})", fontsize=14,
                 fontweight="bold", color="#fbbf24", fontfamily="sans-serif")
        for mi, macro in enumerate(macros[:8]):
            py -= 0.032
            mg = macro.get("genes", [])
            chain = " → ".join(g.get("symbol", "?") for g in mg)
            if len(chain) > 65:
                chain = chain[:62] + "..."
            arch = macro.get("architecture", "").replace("_", " ")
            rax.text(0.05, py, f"{mi+1}. {arch}",
                     fontsize=8, va="center", color=TEXT_COLOR,
                     fontfamily="sans-serif", fontweight="bold")
            rax.text(0.05, py - 0.014, chain,
                     fontsize=6, va="center", color="#fbbf24",
                     fontfamily="sans-serif", alpha=0.8)
        if len(macros) > 8:
            py -= 0.025
            rax.text(0.05, py, f"... and {len(macros) - 8} more",
                     fontsize=7, va="center", color=SUBTLE_COLOR,
                     fontfamily="sans-serif")
        py -= 0.02

    # Satellites
    if satellites:
        py -= 0.02
        rax.text(0.05, py, f"SATELLITE CORES ({len(satellites)})", fontsize=14,
                 fontweight="bold", color=TEXT_COLOR, fontfamily="sans-serif")
        for si, sat in enumerate(satellites[:12]):
            py -= 0.022
            gids = sat.get("_gene_ids", [])
            label = " / ".join(syms.get(g, g) for g in gids)
            if len(label) > 35:
                label = label[:32] + "..."
            n_genes_sat = sat["node_count"]
            rax.text(0.05, py, label, fontsize=8, va="center", color=TEXT_COLOR,
                     fontfamily="sans-serif", fontweight="bold")
            rax.text(0.60, py, f"{n_genes_sat} genes",
                     fontsize=7, va="center", color=SUBTLE_COLOR,
                     fontfamily="sans-serif")
        if len(satellites) > 12:
            py -= 0.022
            rax.text(0.05, py, f"... and {len(satellites) - 12} more",
                     fontsize=7, va="center", color=SUBTLE_COLOR,
                     fontfamily="sans-serif")
        py -= 0.02

    # TF Family legend
    py -= 0.02
    rax.text(0.05, py, "TF FAMILIES", fontsize=14,
             fontweight="bold", color=TEXT_COLOR, fontfamily="sans-serif")
    families_present = sorted({gene_family.get(g, "Other") for g in gene_ids})
    for pi, fam in enumerate(families_present):
        c_ = pi % 2
        r_ = pi // 2
        px = 0.05 + c_ * 0.45
        ppy = py - 0.025 - r_ * 0.023
        col = TF_FAMILY_COLORS.get(fam, "#94a3b8")
        rax.plot(px, ppy, "o", color=col, markersize=7)
        rax.text(px + 0.03, ppy, fam, fontsize=8, va="center",
                 color=TEXT_COLOR, fontfamily="sans-serif")

    # How to read
    n_fam_rows = (len(families_present) + 1) // 2
    py = py - 0.025 - n_fam_rows * 0.023 - 0.03
    rax.text(0.05, py, "HOW TO READ", fontsize=14,
             fontweight="bold", color=TEXT_COLOR, fontfamily="sans-serif")
    py -= 0.018
    rax.text(0.05, py, "Each line = one TF → target regulatory edge",
             fontsize=7, va="center", color=SUBTLE_COLOR,
             fontfamily="sans-serif", style="italic")
    py -= 0.012
    rax.text(0.05, py, "Line color = source TF family",
             fontsize=7, va="center", color=SUBTLE_COLOR,
             fontfamily="sans-serif", style="italic")

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

    node_items = [
        ("Gene node ●", "Color = TF family", None),
        ("White ring", "Junction (2+ circuits)", "#ffffff"),
    ]
    for ni, (sym_text, desc, col) in enumerate(node_items):
        hy = py - 0.025 - (len(line_items) + ni) * 0.025
        sym_col = col if col else TEXT_COLOR
        rax.text(0.05, hy, sym_text, fontsize=7.5, va="center", color=sym_col,
                 fontfamily="sans-serif", fontweight="bold")
        rax.text(0.42, hy, desc, fontsize=7.5, va="center", color=TEXT_COLOR,
                 fontfamily="sans-serif")

    # Save
    out = Path(__file__).resolve().parent.parent / f"{species}_feedback_architecture.png"
    fig.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG_COLOR)
    print(f"Saved: {out}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("species", nargs="?", help="Species name (e.g. human, tomato)")
    parser.add_argument("--all", action="store_true", help="Generate for all species")
    args = parser.parse_args()

    db = sqlite3.connect(str(BACKEND / "data" / "grn.sqlite3"))
    db.execute("PRAGMA foreign_keys = ON")

    if args.all:
        species_list = [r[0] for r in db.execute(
            "SELECT DISTINCT species FROM genes ORDER BY species"
        ).fetchall()]
        species_list = [s for s in species_list if s != "arabidopsis"]
    elif args.species:
        species_list = [args.species]
    else:
        parser.error("Provide a species name or use --all")

    for species in species_list:
        print(f"\nGenerating {species}...")
        generate_diagram(species, db)

    db.close()


if __name__ == "__main__":
    main()
