"""Re-fetch the source data caches so build_db.py can (re)build grn.sqlite3.

The repository does NOT redistribute third-party data (see LICENSE) — this script pulls
it from the original sources into backend/data/. Run once after cloning, then build_db.py.

Tiers (build_db loads whatever caches are present; missing caches just leave that layer
empty, so the app always builds a working *core* atlas):

  core   — genes, interactions, coordinates, orthologs, GO. Network + minutes. Required.
  light  — pathways, traits, sequence-context windows, curated symbols, transcript stores.
           Network + minutes; curated symbols need BLAST+.
  heavy  — expression matrices (kallisto over public RNA-seq, HOURS) and predicted binding
           (motif scans over multi-GB genomes). Need kallisto/BLAST; run per species by
           hand (fetch_expression.py / motif_scan.py). Optional.

Some sources have no scripted fetch (direct downloads) — those are printed with a URL.

Usage: python backend/scripts/fetch_sources.py [--tier core|light|all]
"""
import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
PY = sys.executable

# (label, argv, note). argv forms:
#   [prog, args...]              -> run a fetch script (list-of-lists = several)
#   ("DOWNLOAD", url, filename)  -> direct download into backend/data/
#   None                         -> guidance only (manual step)
CORE = [
    ("TRRUST human network", ("DOWNLOAD",
     "https://www.grnpedia.org/trrust/data/trrust_rawdata.human.tsv",
     "trrust_rawdata.human.tsv"), None),
    ("gene names (mygene)", [PY, "fetch_gene_names.py"], None),
    ("OMA coords + orthologs", [PY, "fetch_genome_data.py"], None),
    ("PLAZA plant coords/orthology/symbols", [PY, "fetch_plaza_data.py"], None),
    ("GO annotations", [PY, "fetch_go.py"], None),
    ("tomato regulation (PlantRegMap)", [PY, "fetch_tomato_regulation.py"], None),
    ("ATRM + arabidopsis regulation", None,
     "manual: backend/data/{atrm_regulations.tsv, regulation_arabidopsis.tsv} (ATRM site; "
     "PlantRegMap, pre-filtered to tf/target/reg/confidence). build_db skips these gracefully "
     "if absent (arabidopsis network + projection then empty)."),
]
LIGHT = [
    ("plant pathways (Plant Reactome)", [PY, "fetch_pathways.py"], None),
    ("human/mouse pathways (mygene)", [PY, "fetch_pathways_animal.py"], None),
    ("GWAS traits", [PY, "fetch_traits.py"],
     "needs the GWAS Catalog associations TSV downloaded to /tmp first (see fetch_traits.py header)."),
    ("sequence-context windows", [[PY, "fetch_seqctx.py", sp] for sp in ("petunia", "arabidopsis")]
     + [[PY, "fetch_tomato_seqctx.py"]], None),
    ("curated UniProt symbols (needs BLAST+ for petunia)",
     [[PY, "fetch_curated_symbols.py", sp] for sp in ("tomato", "petunia")], None),
    ("data-freshness audit", [PY, "check_source_freshness.py"], None),
]


def run(label, argv, note):
    print(f"\n>>> {label}", flush=True)
    if note:
        print(f"    note: {note}", flush=True)
    if argv is None:
        return
    if isinstance(argv, tuple) and argv and argv[0] == "DOWNLOAD":
        _, url, fname = argv
        dest = DATA / fname
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"    downloaded -> {dest} ({dest.stat().st_size} bytes)", flush=True)
        except Exception as e:
            print(f"    ! download failed ({e}) — continuing", flush=True)
        return
    cmds = argv if isinstance(argv[0], list) else [argv]
    for c in cmds:
        r = subprocess.run(c, cwd=HERE)
        if r.returncode != 0:
            print(f"    ! {' '.join(c)} failed (rc={r.returncode}) — continuing", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["core", "light", "all"], default="core")
    args = ap.parse_args()
    print(f"Fetching sources (tier={args.tier}) into backend/data/ ...")
    for label, argv, note in CORE:
        run(label, argv, note)
    if args.tier in ("light", "all"):
        for label, argv, note in LIGHT:
            run(label, argv, note)
    print("\nDone. Now: python backend/scripts/build_db.py")
    print("Heavy layers (expression, predicted binding) are optional and need kallisto/BLAST — "
          "see docs/DEVELOPMENT.md and fetch_expression.py / motif_scan.py.")


if __name__ == "__main__":
    main()
