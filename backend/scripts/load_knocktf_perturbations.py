"""
Load an independent loss-of-function TF-perturbation corpus from KnockTF 2.0.

KnockTF 2.0 (Feng et al., Nucleic Acids Research 2024, PMID 37956336) curates knockdown/
knockout TF expression profiles. Its Arabidopsis table gives genome-wide DEGs after a TF is
disrupted — loss-of-function, the complement to ConnecTF's gain-of-function induction. These
are independent of the atlas edges, so they are clean ground truth for perturbation
calibration.

Direction convention: loss-of-function. A gene that goes DOWN when the TF is removed is
normally activated by it; perturbation_compare already treats perturbation_type='knockdown'
that way (activation -> target down).

Rows are kept when KnockTF's own DE call (`up_down` in {1 up, 2 down}) is set and both the TF
(resolved from symbol/alias) and the affected gene (an AT locus) are in the atlas.

Auto-downloads the ~90 MB table if absent. Idempotent: clears prior 'knocktf' rows.

Usage:
    backend/venv/bin/python backend/scripts/load_knocktf_perturbations.py [/path/to/knocktf_arabidopsis.txt]
"""
import csv
import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
DEFAULT_FILE = Path("/tmp/knocktf_arabidopsis.txt")
URL = "http://www.licpathway.net/KnockTFv2/public/download_anno/knocktf_v2_main_arabidopsis.txt"
DATASET_LABEL = "knocktf"
PMID = "37956336"


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


def tf_resolver(conn):
    atlas = {r[0] for r in conn.execute("SELECT id FROM genes WHERE species='arabidopsis'")}
    sym = {}
    for gid, s in conn.execute(
            "SELECT id, symbol FROM genes WHERE species='arabidopsis' AND symbol IS NOT NULL"):
        sym.setdefault(s.upper(), gid)
    for gid, a in conn.execute(
            "SELECT g.id, ga.alias FROM gene_aliases ga JOIN genes g ON g.id = ga.gene_id "
            "WHERE g.species='arabidopsis'"):
        sym.setdefault(a.upper(), gid)

    def resolve(tok):
        tok = (tok or "").strip().upper()
        if tok in atlas:
            return tok
        return sym.get(tok)

    return atlas, resolve


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FILE
    if not path.exists():
        print(f"Downloading KnockTF Arabidopsis table (~90 MB) -> {path}")
        try:
            urllib.request.urlretrieve(URL, path)
        except Exception as e:
            print(f"  download failed ({e}); skipping (optional layer).")
            return

    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)
    conn.execute("DELETE FROM perturbation_observations WHERE dataset_label = ?", (DATASET_LABEL,))
    conn.commit()
    atlas, resolve = tf_resolver(conn)

    rows = []
    kept_tfs = set()
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for r in reader:
            up_down = (r.get("up_down") or "").strip()
            if up_down not in ("1", "2"):   # KnockTF's own DE call: 1 up, 2 down
                continue
            tf = resolve(r.get("TF"))
            gene = (r.get("Gene") or "").strip().upper()
            if not tf or gene not in atlas or gene == tf:
                continue
            try:
                log2fc = float(r.get("Log2FC"))
            except (TypeError, ValueError):
                continue
            meta = json.dumps({"pmid": PMID, "source": "KnockTF 2.0",
                               "assay": "loss-of-function (knockdown/knockout)",
                               "sample_id": r.get("Sample_ID")})
            rows.append(("arabidopsis", tf, "knockdown", gene, log2fc, 1, DATASET_LABEL, meta))
            kept_tfs.add(tf)

    conn.executemany(
        "INSERT INTO perturbation_observations "
        "(species, perturbed_gene, perturbation_type, affected_gene, "
        "observed_log2fc, observed_significant, dataset_label, metadata) VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"Loaded {len(rows):,} KnockTF loss-of-function observations across {len(kept_tfs)} TFs")


if __name__ == "__main__":
    main()
