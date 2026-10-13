"""
Load a literature-grounded perturbation ground-truth corpus for calibration.

Source: the committed, PMID-backed literature edge files
(backend/data/literature_edges_<species>.tsv). Each curated edge documents a
regulatory *direction* (activation/repression) established by the cited study.
We encode each as a loss-of-function observation so the calibration surface has a
real, traceable reference to score atlas predictions against:

  activation edge  TF -> target   =>  knockdown of TF lowers target   (log2fc = -1, down)
  repression edge  TF -> target   =>  knockdown of TF raises target    (log2fc = +1, up)

Honesty note: these are literature-documented directions, not raw magnitudes from a
single independent screen. dataset_label = 'literature_curated' and the source PMID is
stored in metadata so the provenance stays explicit. Magnitudes are direction markers
(+/-1.0); the calibration logic only uses the sign of the change.

Idempotent: clears any previously loaded 'literature_curated' rows before inserting.

Usage:
    backend/venv/bin/python backend/scripts/load_perturbation_truth.py
"""
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
DATASET_LABEL = "literature_curated"

SPECIES_FILES = {
    "arabidopsis": "literature_edges_arabidopsis.tsv",
    "tomato": "literature_edges_tomato.tsv",
    "petunia": "literature_edges_petunia.tsv",
}


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS perturbation_observations (
            obs_id INTEGER PRIMARY KEY AUTOINCREMENT,
            species TEXT NOT NULL, perturbed_gene TEXT NOT NULL,
            perturbation_type TEXT NOT NULL, affected_gene TEXT NOT NULL,
            observed_log2fc REAL, observed_significant INTEGER DEFAULT 0,
            dataset_label TEXT, metadata TEXT)
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_po_species ON perturbation_observations(species)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_po_gene ON perturbation_observations(perturbed_gene)")
    conn.commit()


def parse_edges(path: Path):
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        source, target, reg = parts[0], parts[1], parts[2]
        tag = parts[4] if len(parts) > 4 else ""
        pmid = None
        if "literature:" in tag:
            pmid = [value.strip() for value in tag.split("literature:")[-1].split(",") if value.strip()]
        yield source, target, reg, pmid


def main():
    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)

    # Only clear the rows this loader owns; leave any other imported datasets intact.
    conn.execute("DELETE FROM perturbation_observations WHERE dataset_label = ?", (DATASET_LABEL,))
    conn.commit()

    gene_ids = {r[0] for r in conn.execute("SELECT id FROM genes")}

    total = 0
    skipped = 0
    for species, fname in SPECIES_FILES.items():
        path = DATA_DIR / fname
        if not path.exists():
            print(f"  {species}: {fname} not found, skipping")
            continue
        rows = []
        for source, target, reg, pmid in parse_edges(path):
            # Only keep observations whose genes resolve in the atlas.
            if source not in gene_ids or target not in gene_ids:
                skipped += 1
                continue
            log2fc = -1.0 if reg == "activation" else 1.0 if reg == "repression" else 0.0
            meta = json.dumps({"pmids": pmid or [], "edge_direction": reg,
                               "note": "literature-documented direction (knockdown framing)"})
            rows.append((species, source, "knockdown", target, log2fc, 1, DATASET_LABEL, meta))
        conn.executemany(
            "INSERT INTO perturbation_observations "
            "(species, perturbed_gene, perturbation_type, affected_gene, "
            "observed_log2fc, observed_significant, dataset_label, metadata) "
            "VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        print(f"  {species}: {len(rows)} observations loaded")
        total += len(rows)

    conn.close()
    print(f"\nLoaded {total} literature-curated perturbation observations "
          f"({skipped} skipped: gene not in atlas)")


if __name__ == "__main__":
    main()
