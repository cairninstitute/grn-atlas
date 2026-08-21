"""
Compute per-tissue coexpression weights for regulatory edges.

For each species with expression data, computes Pearson correlation between
TF and target TPM vectors within each tissue group (≥2 samples) and globally.
Stores results in the edge_tissue_weights table of grn.sqlite3.
"""
import gzip
import json
import math
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

SPECIES_WITH_EXPR = ("petunia", "tomato", "arabidopsis")
MIN_SAMPLES = 2
MIN_ABS_R = 0.3


def pearson(x, y):
    n = len(x)
    if n < 2:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    dx = [a - mx for a in x]
    dy = [a - my for a in y]
    num = sum(a * b for a, b in zip(dx, dy))
    d1 = math.sqrt(sum(a * a for a in dx))
    d2 = math.sqrt(sum(a * a for a in dy))
    if d1 == 0 or d2 == 0:
        return 0.0
    return num / (d1 * d2)


def load_expression(species):
    path = DATA_DIR / f"expression_{species}.json.gz"
    if not path.exists():
        return None, None, None
    data = json.loads(gzip.open(path, "rt").read())
    return data["genes"], data["samples"], data.get("meta", {})


def group_samples_by_tissue(samples):
    groups = {}
    for i, s in enumerate(samples):
        tissue = s.get("tissue", "unknown")
        groups.setdefault(tissue, []).append(i)
    return groups


def compute_weights(species, conn):
    genes, samples, meta = load_expression(species)
    if not genes or not samples:
        print(f"  {species}: no expression data, skipping")
        return 0

    tissue_groups = group_samples_by_tissue(samples)
    tissue_groups = {t: idx for t, idx in tissue_groups.items() if len(idx) >= MIN_SAMPLES}
    tissue_groups["_global"] = list(range(len(samples)))

    edges = conn.execute(
        "SELECT i.source_id, i.target_id FROM interactions i "
        "JOIN genes g ON g.id = i.source_id WHERE g.species = ?",
        (species,),
    ).fetchall()

    rows = []
    checked = 0
    for tf, tgt in edges:
        tf_expr = genes.get(tf)
        tgt_expr = genes.get(tgt)
        if not tf_expr or not tgt_expr:
            continue
        checked += 1
        for tissue, indices in tissue_groups.items():
            x = [tf_expr[i] for i in indices]
            y = [tgt_expr[i] for i in indices]
            r = pearson(x, y)
            if abs(r) >= MIN_ABS_R:
                rows.append((tf, tgt, tissue, round(r, 4), species))

    conn.executemany(
        "INSERT OR REPLACE INTO edge_tissue_weights "
        "(source_id, target_id, tissue, coexpression, species) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    print(f"  {species}: {checked:,} edges checked, {len(rows):,} tissue-weight rows inserted "
          f"({len(tissue_groups)} tissue groups)")
    return len(rows)


def main():
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS edge_tissue_weights (
            source_id     TEXT NOT NULL,
            target_id     TEXT NOT NULL,
            tissue        TEXT NOT NULL,
            coexpression  REAL NOT NULL,
            species       TEXT NOT NULL,
            PRIMARY KEY (source_id, target_id, tissue)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_etw_source ON edge_tissue_weights(source_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_etw_species ON edge_tissue_weights(species)")
    conn.execute("DELETE FROM edge_tissue_weights")
    conn.commit()

    total = 0
    for species in SPECIES_WITH_EXPR:
        total += compute_weights(species, conn)

    conn.close()
    print(f"\nTotal tissue-weight rows: {total:,}")


if __name__ == "__main__":
    main()
