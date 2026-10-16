"""
Load independent loss-of-function TF-perturbation corpora from KnockTF 2.0.

KnockTF 2.0 (Feng et al., Nucleic Acids Research 2024, PMID 37956336) curates knockdown/
knockout TF expression profiles. The Arabidopsis, human, and mouse tables give genome-wide
DEGs after a TF is disrupted. These are independent of atlas edges and are stored as
context-specific perturbation observations for calibration.

Direction convention: loss-of-function. A gene that goes DOWN when the TF is removed is
normally activated by it; perturbation_compare already treats perturbation_type='knockdown'
that way (activation -> target down).

Rows are kept when KnockTF's own DE call (`up_down` in {1 up, 2 down}) is set and both the TF
(resolved from symbol/alias) and the affected gene (an AT locus) are in the atlas.

Downloads the selected source atomically if absent and inserts in bounded batches.
Idempotent per species: rows for other species are not removed.

Usage:
    backend/venv/bin/python backend/scripts/load_knocktf_perturbations.py --species arabidopsis
    backend/venv/bin/python backend/scripts/load_knocktf_perturbations.py --species human
    backend/venv/bin/python backend/scripts/load_knocktf_perturbations.py --species all
"""
import argparse
import csv
import json
import sqlite3
import urllib.request
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from perturbation_evidence import ensure_schema as ensure_perturbation_schema  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
DEFAULT_FILE = Path("/tmp/knocktf_arabidopsis.txt")
DATASET_LABEL = "knocktf"
PMID = "37956336"
SPECIES = {
    "arabidopsis": {
        "url": "http://www.licpathway.net/KnockTFv2/public/download_anno/knocktf_v2_main_arabidopsis.txt",
        "path": DEFAULT_FILE,
    },
    "human": {
        "url": "http://www.licpathway.net/KnockTFv2/public/download_anno/knocktf_v2_main_human.txt",
        "path": Path("/tmp/knocktf_human.txt"),
    },
    "mouse": {
        "url": "http://www.licpathway.net/KnockTFv2/public/download_anno/knocktf_v2_main_mouse.txt",
        "path": Path("/tmp/knocktf_mouse.txt"),
    },
}


def ensure_table(conn):
    ensure_perturbation_schema(conn)


def gene_resolver(conn, species):
    atlas = {r[0] for r in conn.execute("SELECT id FROM genes WHERE species=?", (species,))}
    sym = {}
    for gid, s in conn.execute(
            "SELECT id, symbol FROM genes WHERE species=? AND symbol IS NOT NULL", (species,)):
        sym.setdefault(s.upper(), gid)
    for gid, a in conn.execute(
            "SELECT g.id, ga.alias FROM gene_aliases ga JOIN genes g ON g.id = ga.gene_id "
            "WHERE g.species=?", (species,)):
        sym.setdefault(a.upper(), gid)

    def resolve(tok):
        tok = (tok or "").strip().upper()
        if tok in atlas:
            return tok
        return sym.get(tok)

    return atlas, resolve


def load_species(conn, species, path):
    config = SPECIES[species]
    if path.exists():
        try:
            request = urllib.request.Request(config["url"], method="HEAD")
            with urllib.request.urlopen(request, timeout=30) as response:
                expected_size = int(response.headers.get("Content-Length") or 0)
            if expected_size and path.stat().st_size != expected_size:
                print(f"Discarding incomplete KnockTF {species} file ({path.stat().st_size:,}/{expected_size:,} bytes)")
                path.unlink()
        except (OSError, ValueError):
            pass
    if not path.exists():
        print(f"Downloading KnockTF {species} table -> {path}")
        try:
            partial = path.with_suffix(path.suffix + ".part")
            urllib.request.urlretrieve(config["url"], partial)
            partial.replace(path)
        except Exception as e:
            print(f"  download failed ({e}); skipping.")
            return {"species": species, "status": "download_failed", "error": str(e)}

    conn.execute(
        "DELETE FROM perturbation_observations WHERE dataset_label = ? AND species = ?",
        (DATASET_LABEL, species),
    )
    conn.commit()
    atlas, resolve = gene_resolver(conn, species)

    rows = []
    loaded = 0
    skipped = 0
    kept_tfs = set()
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for r in reader:
            up_down = (r.get("up_down") or "").strip()
            if up_down not in ("1", "2"):   # KnockTF's own DE call: 1 up, 2 down
                continue
            tf = resolve(r.get("TF"))
            gene = resolve(r.get("NCBI_Official_Symbol")) or resolve(r.get("Gene")) or resolve(r.get("Ensembl_ID"))
            if not tf or not gene or gene == tf:
                skipped += 1
                continue
            try:
                log2fc = float(r.get("Log2FC"))
            except (TypeError, ValueError):
                continue
            meta = json.dumps({"pmid": PMID, "source": "KnockTF 2.0",
                               "assay": "loss-of-function (knockdown/knockout)",
                               "sample_id": r.get("Sample_ID")})
            rows.append((species, tf, "knockdown", gene, log2fc, 1, DATASET_LABEL, meta))
            kept_tfs.add(tf)
            if len(rows) >= 50_000:
                conn.executemany(
                    "INSERT INTO perturbation_observations "
                    "(species, perturbed_gene, perturbation_type, affected_gene, "
                    "observed_log2fc, observed_significant, dataset_label, metadata) VALUES (?,?,?,?,?,?,?,?)",
                    rows,
                )
                loaded += len(rows)
                rows.clear()
                conn.commit()
    if rows:
        conn.executemany(
            "INSERT INTO perturbation_observations "
            "(species, perturbed_gene, perturbation_type, affected_gene, "
            "observed_log2fc, observed_significant, dataset_label, metadata) VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        loaded += len(rows)
    conn.commit()
    print(f"Loaded {loaded:,} {species} KnockTF observations across {len(kept_tfs)} TFs")
    return {"species": species, "status": "complete", "observations": loaded,
            "tfs": len(kept_tfs), "unmapped": skipped}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path,
                        help="Input path (only valid when loading one species)")
    parser.add_argument("--species", choices=[*SPECIES, "all"], default="arabidopsis")
    args = parser.parse_args()
    species_list = list(SPECIES) if args.species == "all" else [args.species]
    if args.path and len(species_list) != 1:
        parser.error("path can only be used with one --species")

    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)
    results = []
    for species in species_list:
        results.append(load_species(conn, species, args.path or SPECIES[species]["path"]))
    conn.close()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
