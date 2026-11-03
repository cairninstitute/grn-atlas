#!/usr/bin/env python3
"""Generate platform-specific image variants for social media."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path
from PIL import Image

OUT = Path(__file__).resolve().parent

COLORS = {
    "protein": "#3b82f6",
    "dna": "#22c55e",
    "expression": "#f97316",
    "structure": "#a855f7",
    "binding": "#ef4444",
}

TESTED_MODELS = [
    ("ProteinMPNN", 0.995, "protein"),
    ("ESM2-650M", 0.975, "protein"),
    ("Evo2 SAE", 1.000, "dna"),
    ("AlphaFold DB", 0.882, "structure"),
    ("CADD v1.7", 0.851, "dna"),
    ("JASPAR", 0.795, "binding"),
    ("AgroNT", 0.594, "dna"),
    ("Enformer", 0.518, "expression"),
    ("Borzoi", 0.509, "expression"),
    ("Evo2 linear", 0.500, "dna"),
    ("Boltz-2", 0.420, "structure"),
    ("deepTFBS", 0.358, "dna"),
]


def hero_square():
    """Square hero chart for Instagram/Threads (1080x1080)."""
    models = sorted(TESTED_MODELS, key=lambda x: x[1])
    names = [m[0] for m in models]
    aucs = [m[1] for m in models]
    colors = [COLORS[m[2]] for m in models]

    fig, ax = plt.subplots(figsize=(10, 10))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")

    ax.barh(range(len(names)), aucs, color=colors, height=0.65, edgecolor="none")

    for i, (name, auc) in enumerate(zip(names, aucs)):
        ax.text(auc + 0.015, i, f"{auc:.3f}", va="center", ha="left",
                color="white", fontsize=13, fontweight="bold")

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=13, color="white")
    ax.set_xlim(0, 1.15)
    ax.set_xlabel("Best AUC", fontsize=14, color="white")

    ax.axvline(x=0.5, color="#64748b", linestyle="--", linewidth=1.5, alpha=0.7)
    ax.text(0.505, len(names) - 0.5, "chance", color="#94a3b8", fontsize=11,
            va="bottom", ha="left")

    legend_patches = [
        mpatches.Patch(color=COLORS["protein"], label="Protein"),
        mpatches.Patch(color=COLORS["dna"], label="DNA"),
        mpatches.Patch(color=COLORS["expression"], label="Expression"),
        mpatches.Patch(color=COLORS["structure"], label="Structure"),
        mpatches.Patch(color=COLORS["binding"], label="Binding"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=11,
              facecolor="#1e293b", edgecolor="#334155", labelcolor="white")

    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("#334155")

    fig.suptitle("12 Models. 162K Edges.\nZero Regulatory Predictions.",
                 fontsize=20, fontweight="bold", color="white", y=0.97)

    fig.tight_layout(rect=[0, 0, 1, 0.91])
    fig.savefig(OUT / "model_survey_hero_square.png", dpi=108,
                bbox_inches="tight", facecolor="#0f172a")
    plt.close(fig)
    print(f"  Saved model_survey_hero_square.png")


def proteinmpnn_square():
    """Square ProteinMPNN dot plot for Instagram/Threads (1080x1080)."""
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

    fig, ax = plt.subplots(figsize=(10, 10))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")

    np.random.seed(42)
    tf_jitter = np.random.normal(0, 0.08, len(tf_recovery))
    nontf_jitter = np.random.normal(0, 0.08, len(nontf_recovery))

    ax.scatter(tf_recovery, tf_jitter + 1.2, color="#ef4444", s=100, alpha=0.8,
               edgecolors="white", linewidths=0.5, zorder=3)
    ax.scatter(nontf_recovery, nontf_jitter + 2.8, color="#3b82f6", s=100, alpha=0.8,
               edgecolors="white", linewidths=0.5, zorder=3)

    tf_mean = np.mean(tf_recovery)
    nontf_mean = np.mean(nontf_recovery)
    ax.axvline(tf_mean, color="#ef4444", linestyle="--", linewidth=2, alpha=0.6)
    ax.axvline(nontf_mean, color="#3b82f6", linestyle="--", linewidth=2, alpha=0.6)

    ax.text(tf_mean, 0.2, f"TF mean\n{tf_mean:.3f}", ha="center", color="#ef4444",
            fontsize=14, fontweight="bold")
    ax.text(nontf_mean, 3.7, f"Enzyme mean\n{nontf_mean:.3f}", ha="center",
            color="#3b82f6", fontsize=14, fontweight="bold")

    ax.set_yticks([1.2, 2.8])
    ax.set_yticklabels(["Transcription\nfactors (n=29)", "Housekeeping\nenzymes (n=20)"],
                       fontsize=14, color="white")
    ax.set_xlabel("ProteinMPNN Sequence Recovery", fontsize=14, color="white")
    ax.set_xlim(0.1, 0.7)
    ax.set_ylim(-0.2, 4.2)

    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("#334155")

    fig.suptitle("AUC = 0.995\nTF proteins are structurally flexible",
                 fontsize=20, color="white", fontweight="bold", y=0.97)

    fig.tight_layout(rect=[0, 0, 1, 0.91])
    fig.savefig(OUT / "model_survey_proteinmpnn_dots_square.png", dpi=108,
                bbox_inches="tight", facecolor="#0f172a")
    plt.close(fig)
    print(f"  Saved model_survey_proteinmpnn_dots_square.png")


def heatmap_square():
    """Square species heatmap for Instagram (1080x1080)."""
    models_sp = [
        "ProteinMPNN", "ESM2", "AlphaFold", "CADD", "Evo2 SAE",
        "JASPAR", "Enformer", "Borzoi", "deepTFBS", "AgroNT", "Boltz-2",
    ]
    species = ["Arab.", "Human", "Mouse", "Rice", "Petunia", "Potato"]

    data = np.full((len(models_sp), len(species)), np.nan)
    data[0, 0] = 0.995; data[0, 1] = 0.995
    data[1, 0] = 0.959; data[1, 1] = 0.821; data[1, 2] = 0.882; data[1, 3] = 0.975
    data[2, 0] = 0.882; data[2, 1] = 0.847; data[2, 2] = 0.784
    data[3, 1] = 0.851
    data[4, 0] = 0.889; data[4, 1] = 0.545; data[4, 2] = 0.500; data[4, 3] = 0.636; data[4, 5] = 0.763
    data[5, 0] = 0.795; data[5, 4] = 0.715
    data[6, 1] = 0.518
    data[7, 1] = 0.509
    data[8, 0] = 0.358
    data[9, 0] = 0.594
    data[10, 0] = 0.420; data[10, 1] = 0.520

    fig, ax = plt.subplots(figsize=(10, 10))

    cmap = plt.cm.RdYlGn.copy()
    cmap.set_bad("#e5e7eb")

    im = ax.imshow(data, cmap=cmap, aspect="auto", vmin=0.3, vmax=1.0)

    for i in range(len(models_sp)):
        for j in range(len(species)):
            val = data[i, j]
            if not np.isnan(val):
                color = "white" if val < 0.55 or val > 0.85 else "black"
                ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                        fontsize=11, fontweight="bold", color=color)

    ax.set_xticks(range(len(species)))
    ax.set_xticklabels(species, fontsize=13, rotation=30, ha="right")
    ax.set_yticks(range(len(models_sp)))
    ax.set_yticklabels(models_sp, fontsize=13)

    cbar = plt.colorbar(im, ax=ax, shrink=0.7)
    cbar.set_label("AUC", fontsize=12)

    ax.set_title("Species coverage:\neach model works in its training domain",
                 fontsize=16, fontweight="bold", pad=15)

    fig.tight_layout()
    fig.savefig(OUT / "model_survey_species_heatmap_square.png", dpi=108,
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved model_survey_species_heatmap_square.png")


def quadrant_square():
    """Square quadrant for Instagram (1080x1080)."""
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

    label_offsets = {
        "Evo2 SAE": (-0.02, 0.025),
        "ProteinMPNN": (0.02, -0.035),
        "ESM2": (0.02, 0.02),
        "Borzoi": (0.02, -0.04),
        "Enformer": (0.02, 0.03),
        "CADD": (0.02, -0.035),
        "AlphaFold": (0.02, 0.02),
    }

    fig, ax = plt.subplots(figsize=(10, 10))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fafafa")

    ax.axhline(0.5, color="#d1d5db", linewidth=1, linestyle="-")
    ax.axvline(0.5, color="#d1d5db", linewidth=1, linestyle="-")

    for name, x, y, cat in models_quad:
        ax.scatter(x, y, color=COLORS[cat], s=140, zorder=3,
                   edgecolors="white", linewidths=1.5)
        ox, oy = label_offsets.get(name, (0.02, 0.02))
        ax.annotate(name, (x + ox, y + oy), fontsize=10,
                    fontweight="bold", color="#374151")

    ax.fill_between([0.5, 1.0], 0.7, 1.05, alpha=0.08, color="#22c55e")
    ax.text(0.75, 0.92, "The gap", fontsize=18, ha="center", va="center",
            color="#9ca3af", fontstyle="italic", fontweight="bold")
    ax.text(0.75, 0.84, "No model reaches here", fontsize=11,
            ha="center", va="center", color="#9ca3af")

    ax.set_xlabel("Protein characterization ← → Regulatory prediction",
                  fontsize=13, color="#374151", fontweight="bold")
    ax.set_ylabel("Best AUC on tested task", fontsize=13, color="#374151",
                  fontweight="bold")
    ax.set_xlim(0.1, 1.0)
    ax.set_ylim(0.3, 1.05)

    legend_patches = [
        mpatches.Patch(color=COLORS["protein"], label="Protein"),
        mpatches.Patch(color=COLORS["dna"], label="DNA"),
        mpatches.Patch(color=COLORS["expression"], label="Expression"),
        mpatches.Patch(color=COLORS["structure"], label="Structure"),
        mpatches.Patch(color=COLORS["binding"], label="Binding"),
    ]
    ax.legend(handles=legend_patches, loc="lower left", fontsize=10,
              framealpha=0.9)

    ax.set_title("Good at characterization,\nblind to regulation",
                 fontsize=16, color="#1f2937", fontweight="bold", pad=15)

    fig.tight_layout()
    fig.savefig(OUT / "model_survey_linkedin_quadrant_square.png", dpi=108,
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved model_survey_linkedin_quadrant_square.png")


def hero_facebook():
    """Facebook hero crop: 1200x630 from the existing hero image."""
    img = Image.open(OUT / "model_survey_hero.png")
    w, h = img.size
    target_ratio = 1200 / 630
    current_ratio = w / h
    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    img = img.resize((1200, 630), Image.LANCZOS)
    img.save(OUT / "model_survey_hero_facebook.png")
    print(f"  Saved model_survey_hero_facebook.png (1200x630)")


if __name__ == "__main__":
    print("Generating platform-specific images...")
    hero_square()
    proteinmpnn_square()
    heatmap_square()
    quadrant_square()
    hero_facebook()
    print("Done!")
