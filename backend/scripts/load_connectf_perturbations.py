"""
Load an independent TF-perturbation ground-truth corpus from ConnecTF.

ConnecTF (Brooks et al., Plant Physiology 2021, PMID 33631799) ships per-TF DESeq2
differential-expression results from the inducible TARGET assay (Bargmann et al. 2013) —
a transcription factor is induced in root protoplasts (Dex, +cycloheximide) and genome-wide
log2 fold-changes vs an empty-vector control are measured. These are real, measured
perturbation outcomes, independent of the atlas's curated/DAP-seq edges, which is what the
calibration surface needs.

Direction convention (important): the TARGET assay is GAIN-of-function (the TF is induced),
so a positive log2FC means the TF *activates* the gene. Observations are therefore loaded
with perturbation_type='induction' and perturbation_compare treats induction as the inverse
of a knockout (activation edge -> target up).

Data files: <TF_id>_..._DESEQ2.csv / _DESeq2*.csv under the ConnecTF release, columns
(gene, log2FC, padj). Only significant rows (padj < 0.05) whose TF and target both resolve
in the atlas are kept.

Idempotent: clears previously loaded 'connectf_target' rows first. Skips gracefully if the
ConnecTF release is not present (same optional download as `make enrich`).

Usage:
    backend/venv/bin/python backend/scripts/load_connectf_perturbations.py [/path/to/connectf_data_release_v1]
"""
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
DEFAULT_RELEASE = Path("/tmp/connectf_data_release_v1")
DATASET_LABEL = "connectf_target"
PADJ_CUTOFF = 0.05
PMID = "33631799"
TF_RE = re.compile(r"^(AT[1-5CM]G\d{5})", re.IGNORECASE)


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


def main():
    release = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RELEASE
    data_dir = release / "arabidopsis" / "data"
    if not data_dir.is_dir():
        print(f"ConnecTF release not found at {release} — skipping (optional, like `make enrich`).")
        print("  Download: curl -L -o /tmp/connectf_data.tar.gz "
              "https://connectf.s3.amazonaws.com/connectf_data_release_v1.tar.gz && "
              "tar xzf /tmp/connectf_data.tar.gz -C /tmp")
        return

    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)
    conn.execute("DELETE FROM perturbation_observations WHERE dataset_label = ?", (DATASET_LABEL,))
    conn.commit()
    atlas_genes = {r[0] for r in conn.execute("SELECT id FROM genes WHERE species='arabidopsis'")}

    deseq_files = sorted(p for p in data_dir.glob("*.csv") if "deseq2" in p.name.lower())
    print(f"Found {len(deseq_files)} ConnecTF DESeq2 perturbation experiments")

    total = experiments = skipped_tf = 0
    for path in deseq_files:
        m = TF_RE.match(path.name)
        if not m:
            continue
        tf = m.group(1).upper()
        if tf not in atlas_genes:
            skipped_tf += 1
            continue
        rows = []
        with path.open() as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            for row in reader:
                if len(row) < 3:
                    continue
                gene = row[0].strip().strip('"').upper()
                try:
                    log2fc = float(row[1])
                    padj = float(row[2])
                except ValueError:
                    continue
                if padj >= PADJ_CUTOFF or gene not in atlas_genes or gene == tf:
                    continue
                meta = json.dumps({"pmid": PMID, "source": "ConnecTF inducible TARGET assay",
                                   "assay": "gain-of-function induction", "experiment": path.stem})
                rows.append(("arabidopsis", tf, "induction", gene, log2fc, 1, DATASET_LABEL, meta))
        if rows:
            conn.executemany(
                "INSERT INTO perturbation_observations "
                "(species, perturbed_gene, perturbation_type, affected_gene, "
                "observed_log2fc, observed_significant, dataset_label, metadata) "
                "VALUES (?,?,?,?,?,?,?,?)", rows)
            conn.commit()
            experiments += 1
            total += len(rows)

    n_tf = len(set(r[0] for r in conn.execute(
        "SELECT perturbed_gene FROM perturbation_observations WHERE dataset_label=?", (DATASET_LABEL,))))
    conn.close()
    print(f"Loaded {total:,} significant perturbation observations "
          f"from {experiments} experiments ({n_tf} distinct TFs); {skipped_tf} experiments' TF not in atlas")


if __name__ == "__main__":
    main()
