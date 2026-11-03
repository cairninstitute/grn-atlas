#!/usr/bin/env python3
"""Generate visuals for the deep learning model survey blog post."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)

COLORS = {
    "protein": "#3b82f6",
    "dna": "#22c55e",
    "expression": "#f97316",
    "structure": "#a855f7",
    "not_tested": "#9ca3af",
    "binding": "#ef4444",
}

# ── Data ──────────────────────────────────────────────────────────────
MODELS = [
    # (name, best_auc, task_desc, category)
    ("ProteinMPNN", 0.995, "TF vs enzyme designability", "protein"),
    ("ESM2-650M", 0.975, "TF classification (rice)", "protein"),
    ("Evo2 SAE", 1.000, "Species classification", "dna"),
    ("AlphaFold DB", 0.882, "TF structural confidence", "structure"),
    ("CADD v1.7", 0.851, "TSS vs intergenic (human)", "dna"),
    ("JASPAR", 0.795, "Binding prediction (arab.)", "binding"),
    ("AgroNT", 0.594, "Binding (weak, overfits)", "dna"),
    ("Enformer", 0.518, "Binding (large-scale)", "expression"),
    ("Borzoi", 0.509, "Binding (chance level)", "expression"),
    ("Evo2 linear", 0.500, "Binding (no signal)", "dna"),
    ("Boltz-2", 0.420, "Binding (no signal)", "structure"),
    ("deepTFBS", 0.358, "Binding (anti-discriminates)", "dna"),
    ("SpliceAI", None, "Infrastructure blocked", "not_tested"),
    ("Geneformer", None, "Needs scRNA-seq data", "not_tested"),
    ("RFdiffusion", None, "Wrong task (de novo design)", "not_tested"),
    ("DiffDock", None, "Wrong task (small molecule)", "not_tested"),
]


def fig1_hero_bar_chart():
    """Horizontal bar chart: tested models only, ranked by best AUC."""
    tested = [(n, a, t, c) for n, a, t, c in MODELS if a is not None]
    tested.sort(key=lambda x: x[1])
    names = [m[0] for m in tested]
    aucs = [m[1] for m in tested]
    colors = [COLORS[m[3]] for m in tested]

    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")

    bars = ax.barh(range(len(names)), aucs, color=colors, height=0.7, edgecolor="none")

    for i, (name, auc) in enumerate(zip(names, aucs)):
        ax.text(auc + 0.015, i, f"{auc:.3f}", va="center", ha="left",
                color="white", fontsize=11, fontweight="bold")

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=12, color="white")
    ax.set_xlim(0, 1.15)
    ax.set_xlabel("Best AUC", fontsize=13, color="white")

    ax.axvline(x=0.5, color="#64748b", linestyle="--", linewidth=1.5, alpha=0.7)
    ax.text(0.505, len(names) - 0.5, "chance", color="#94a3b8", fontsize=10,
            va="bottom", ha="left")

    ax.set_ylim(-0.5, len(names) - 0.5 + 0.5)

    legend_patches = [
        mpatches.Patch(color=COLORS["protein"], label="Protein model"),
        mpatches.Patch(color=COLORS["dna"], label="DNA model"),
        mpatches.Patch(color=COLORS["expression"], label="Expression model"),
        mpatches.Patch(color=COLORS["structure"], label="Structure model"),
        mpatches.Patch(color=COLORS["binding"], label="Binding (classical)"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=10,
              facecolor="#1e293b", edgecolor="#334155", labelcolor="white")

    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("#334155")

    fig.suptitle("12 Models. 162K Edges. Zero Regulatory Predictions.",
                 fontsize=18, fontweight="bold", color="white", y=0.97)
    ax.set_title("Each model's best AUC on its published task — tested on GRN-Atlas data",
                 fontsize=11, color="#94a3b8", pad=10)

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUT / "model_survey_hero.png", dpi=200, bbox_inches="tight",
                facecolor="#0f172a")
    plt.close(fig)
    print(f"  Saved {OUT / 'model_survey_hero.png'}")


def fig2_twitter_top6():
    """Simplified top-6 bar chart for Twitter."""
    top6 = [
        ("ProteinMPNN", 0.995, "protein"),
        ("ESM2", 0.975, "protein"),
        ("Evo2 SAE", 1.000, "dna"),
        ("AlphaFold", 0.882, "structure"),
        ("CADD", 0.851, "dna"),
        ("JASPAR", 0.795, "binding"),
    ]
    top6.sort(key=lambda x: x[1])

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")

    names = [t[0] for t in top6]
    aucs = [t[1] for t in top6]
    colors = [COLORS[t[2]] for t in top6]

    ax.barh(range(len(names)), aucs, color=colors, height=0.6)

    for i, (n, a) in enumerate(zip(names, aucs)):
        ax.text(a + 0.02, i, f"{a:.3f}", va="center", color="white",
                fontsize=14, fontweight="bold")

    ax.axvline(x=0.5, color="#ef4444", linestyle="--", linewidth=2, alpha=0.8)
    ax.text(0.51, -0.7, "chance", color="#ef4444", fontsize=12, fontweight="bold")

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=14, color="white", fontweight="bold")
    ax.set_xlim(0, 1.15)

    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(bottom=False, left=False)

    ax.set_title("Top models — best AUC on published task",
                 fontsize=14, color="white", fontweight="bold", pad=15)

    fig.tight_layout()
    fig.savefig(OUT / "model_survey_twitter_top6.png", dpi=200,
                bbox_inches="tight", facecolor="#0f172a")
    plt.close(fig)
    print(f"  Saved {OUT / 'model_survey_twitter_top6.png'}")


def fig3_proteinmpnn_dotplot():
    """ProteinMPNN recovery dot plot: TFs vs housekeeping enzymes."""
    tf_recovery = [
        0.229, 0.405, 0.251, 0.335, 0.303, 0.228, 0.300, 0.195, 0.211,
        0.274, 0.242, 0.218, 0.389, 0.275, 0.188, 0.180, 0.280, 0.180,
        0.218, 0.333, 0.203, 0.252, 0.236, 0.188, 0.348, 0.286, 0.458,
        0.320, 0.280,
    ]
    nontf_recovery = [
        0.540, 0.536, 0.446, 0.501, 0.498, 0.563, 0.597, 0.524, 0.555,
        0.550, 0.590, 0.471, 0.624, 0.565, 0.474, 0.528, 0.506, 0.423,
        0.407, 0.488,
    ]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")

    np.random.seed(42)
    tf_jitter = np.random.normal(0, 0.06, len(tf_recovery))
    nontf_jitter = np.random.normal(0, 0.06, len(nontf_recovery))

    ax.scatter(tf_recovery, tf_jitter + 1, color="#ef4444", s=80, alpha=0.8,
               edgecolors="white", linewidths=0.5, zorder=3)
    ax.scatter(nontf_recovery, nontf_jitter + 2, color="#3b82f6", s=80, alpha=0.8,
               edgecolors="white", linewidths=0.5, zorder=3)

    tf_mean = np.mean(tf_recovery)
    nontf_mean = np.mean(nontf_recovery)
    ax.axvline(tf_mean, color="#ef4444", linestyle="--", linewidth=2, alpha=0.6)
    ax.axvline(nontf_mean, color="#3b82f6", linestyle="--", linewidth=2, alpha=0.6)

    ax.text(tf_mean, 0.3, f"TF mean\n{tf_mean:.3f}", ha="center", color="#ef4444",
            fontsize=11, fontweight="bold")
    ax.text(nontf_mean, 2.75, f"Enzyme mean\n{nontf_mean:.3f}", ha="center",
            color="#3b82f6", fontsize=11, fontweight="bold")

    ax.set_yticks([1, 2])
    ax.set_yticklabels(["Transcription\nfactors (n=29)", "Housekeeping\nenzymes (n=20)"],
                       fontsize=12, color="white")
    ax.set_xlabel("ProteinMPNN Sequence Recovery", fontsize=13, color="white")
    ax.set_xlim(0.1, 0.7)
    ax.set_ylim(0, 3.2)

    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("#334155")

    ax.set_title("AUC = 0.995 — TF proteins are structurally flexible",
                 fontsize=14, color="white", fontweight="bold", pad=15)

    fig.tight_layout()
    fig.savefig(OUT / "model_survey_proteinmpnn_dots.png", dpi=200,
                bbox_inches="tight", facecolor="#0f172a")
    plt.close(fig)
    print(f"  Saved {OUT / 'model_survey_proteinmpnn_dots.png'}")


def fig4_linkedin_quadrant():
    """2x2 quadrant: protein characterization vs regulatory prediction."""
    # x-axis: left = characterization, right = regulatory prediction
    models_quad = [
        ("ProteinMPNN", 0.15, 0.995, "protein"),
        ("ESM2", 0.22, 0.975, "protein"),
        ("AlphaFold", 0.27, 0.882, "structure"),
        ("Evo2 SAE", 0.13, 1.000, "dna"),
        ("CADD", 0.24, 0.851, "dna"),
        ("JASPAR", 0.42, 0.795, "binding"),
        ("Enformer", 0.38, 0.518, "expression"),
        ("Borzoi", 0.36, 0.509, "expression"),
        ("AgroNT", 0.35, 0.594, "dna"),
        ("deepTFBS", 0.33, 0.358, "dna"),
        ("Boltz-2", 0.40, 0.420, "structure"),
    ]

    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fafafa")

    ax.axhline(0.5, color="#d1d5db", linewidth=1, linestyle="-")
    ax.axvline(0.5, color="#d1d5db", linewidth=1, linestyle="-")

    label_offsets = {
        "Evo2 SAE": (-0.02, 0.025),
        "ProteinMPNN": (0.02, -0.035),
        "ESM2": (0.02, 0.02),
        "Borzoi": (0.02, -0.04),
        "Enformer": (0.02, 0.03),
        "CADD": (0.02, -0.035),
        "AlphaFold": (0.02, 0.02),
    }
    for name, x, y, cat in models_quad:
        ax.scatter(x, y, color=COLORS[cat], s=120, zorder=3,
                   edgecolors="white", linewidths=1.5)
        ox, oy = label_offsets.get(name, (0.02, 0.02))
        ax.annotate(name, (x + ox, y + oy), fontsize=9,
                    fontweight="bold", color="#374151")

    ax.fill_between([0.5, 1.0], 0.7, 1.05, alpha=0.08, color="#22c55e")
    ax.text(0.75, 0.95, "The gap", fontsize=16, ha="center", va="center",
            color="#9ca3af", fontstyle="italic", fontweight="bold")
    ax.text(0.75, 0.88, "No model reaches here", fontsize=10,
            ha="center", va="center", color="#9ca3af")

    ax.set_xlabel("Protein characterization ← → Regulatory prediction",
                  fontsize=12, color="#374151", fontweight="bold")
    ax.set_ylabel("Best AUC on tested task", fontsize=12, color="#374151",
                  fontweight="bold")
    ax.set_xlim(0.1, 1.0)
    ax.set_ylim(0.3, 1.05)

    legend_patches = [
        mpatches.Patch(color=COLORS["protein"], label="Protein"),
        mpatches.Patch(color=COLORS["dna"], label="DNA"),
        mpatches.Patch(color=COLORS["expression"], label="Expression"),
        mpatches.Patch(color=COLORS["structure"], label="Structure"),
        mpatches.Patch(color=COLORS["binding"], label="Binding (classical)"),
    ]
    ax.legend(handles=legend_patches, loc="lower left", fontsize=9,
              framealpha=0.9)

    ax.set_title("Deep learning models: good at characterization, blind to regulation",
                 fontsize=14, color="#1f2937", fontweight="bold", pad=15)

    fig.tight_layout()
    fig.savefig(OUT / "model_survey_linkedin_quadrant.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {OUT / 'model_survey_linkedin_quadrant.png'}")


def fig5_species_heatmap():
    """Species coverage heatmap: models x species, colored by AUC."""
    models_sp = [
        "ProteinMPNN", "ESM2", "AlphaFold", "CADD", "Evo2 SAE",
        "JASPAR", "Enformer", "Borzoi", "deepTFBS", "AgroNT", "Boltz-2",
    ]
    species = ["Arabidopsis", "Human", "Mouse", "Rice",
               "Petunia", "Potato"]

    data = np.full((len(models_sp), len(species)), np.nan)
    # ProteinMPNN: mixed arab+human
    data[0, 0] = 0.995; data[0, 1] = 0.995
    # ESM2
    data[1, 0] = 0.959; data[1, 1] = 0.821; data[1, 2] = 0.882; data[1, 3] = 0.975
    # AlphaFold
    data[2, 0] = 0.882; data[2, 1] = 0.847; data[2, 2] = 0.784
    # CADD (human only)
    data[3, 1] = 0.851
    # Evo2 SAE (arabidopsis primary, potato 0.763, rice 0.636, human 0.545, mouse 0.500)
    data[4, 0] = 0.889; data[4, 1] = 0.545; data[4, 2] = 0.500; data[4, 3] = 0.636; data[4, 5] = 0.763
    # JASPAR
    data[5, 0] = 0.795; data[5, 4] = 0.715
    # Enformer (human only)
    data[6, 1] = 0.518
    # Borzoi (human only)
    data[7, 1] = 0.509
    # deepTFBS (arab only)
    data[8, 0] = 0.358
    # AgroNT (arab only)
    data[9, 0] = 0.594
    # Boltz-2 (arab+human)
    data[10, 0] = 0.420; data[10, 1] = 0.520

    fig, ax = plt.subplots(figsize=(12, 7))

    cmap = plt.cm.RdYlGn.copy()
    cmap.set_bad("#e5e7eb")

    im = ax.imshow(data, cmap=cmap, aspect="auto", vmin=0.3, vmax=1.0)

    for i in range(len(models_sp)):
        for j in range(len(species)):
            val = data[i, j]
            if not np.isnan(val):
                color = "white" if val < 0.55 or val > 0.85 else "black"
                ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                        fontsize=9, fontweight="bold", color=color)

    ax.set_xticks(range(len(species)))
    ax.set_xticklabels(species, fontsize=11, rotation=30, ha="right")
    ax.set_yticks(range(len(models_sp)))
    ax.set_yticklabels(models_sp, fontsize=11)

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("AUC", fontsize=11)

    ax.set_title("Species coverage: each model works in its training domain",
                 fontsize=14, fontweight="bold", pad=15)

    fig.tight_layout()
    fig.savefig(OUT / "model_survey_species_heatmap.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {OUT / 'model_survey_species_heatmap.png'}")


def fig6_pattern_diagram():
    """Three-column pattern diagram showing the gap."""
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")

    cols = [
        (2, "Protein Models", ["ESM2", "ProteinMPNN", "AlphaFold"],
         "TF characterization", COLORS["protein"]),
        (6, "DNA Models", ["Evo2", "CADD", "JASPAR", "AgroNT"],
         "Sequence classification", COLORS["dna"]),
        (10, "Expression Models", ["Enformer", "Borzoi"],
         "Expression prediction", COLORS["expression"]),
    ]

    for cx, title, models, capability, color in cols:
        ax.add_patch(plt.Rectangle((cx - 1.3, 3.5), 2.6, 2.2, facecolor=color,
                                   alpha=0.15, edgecolor=color, linewidth=2,
                                   zorder=1))
        ax.text(cx, 5.3, title, ha="center", va="center", fontsize=12,
                fontweight="bold", color=color)
        for i, m in enumerate(models):
            ax.text(cx, 4.8 - i * 0.35, m, ha="center", va="center",
                    fontsize=9, color="#4b5563")

        ax.annotate("", xy=(cx, 2.5), xytext=(cx, 3.4),
                    arrowprops=dict(arrowstyle="->", color=color, lw=2))
        ax.add_patch(plt.Rectangle((cx - 1.3, 1.8), 2.6, 0.7, facecolor=color,
                                   alpha=0.1, edgecolor=color, linewidth=1.5,
                                   linestyle="--"))
        ax.text(cx, 2.15, capability, ha="center", va="center", fontsize=10,
                color=color, fontweight="bold")

    # Center target
    ax.add_patch(plt.Rectangle((3.5, 0.2), 5, 1.2, facecolor="#fef2f2",
                                edgecolor="#ef4444", linewidth=2.5,
                                linestyle="-", zorder=2))
    ax.text(6, 0.8, "Regulatory Edge Prediction", ha="center", va="center",
            fontsize=14, fontweight="bold", color="#dc2626")
    ax.text(6, 0.4, "\"This TF controls that gene\"", ha="center", va="center",
            fontsize=10, color="#9ca3af", fontstyle="italic")

    # X marks for no arrows reaching center
    for cx in [2, 6, 10]:
        ax.plot([cx - 0.15, cx + 0.15], [1.55, 1.75], color="#ef4444",
                linewidth=2.5, zorder=3)
        ax.plot([cx - 0.15, cx + 0.15], [1.75, 1.55], color="#ef4444",
                linewidth=2.5, zorder=3)

    fig.savefig(OUT / "model_survey_pattern_diagram.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {OUT / 'model_survey_pattern_diagram.png'}")


if __name__ == "__main__":
    print("Generating model survey visuals...")
    fig1_hero_bar_chart()
    fig2_twitter_top6()
    fig3_proteinmpnn_dotplot()
    fig4_linkedin_quadrant()
    fig5_species_heatmap()
    print("Done!")
