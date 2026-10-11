"""
Cache JASPAR position weight matrices for allele-specific affinity scoring.

The motif scanner (motif_scan.py) scored promoter sites against JASPAR plant PWMs but
only stored the resulting hits, not the matrices. grn-allele-affinity needs the matrices
to rescore a site when a single base changes (ref -> alt). This step fetches the PFM for
every jaspar_id referenced by the atlas `motifs` table from the JASPAR REST API and
converts it to a log-odds matrix on the SAME scale the scanner used
(pseudocount 0.8, uniform 0.25 background, log2), then writes:

    backend/data/motif_pwms.json.gz

keyed by motif_id -> {"jaspar_id", "width", "lom": [[A,C,G,T], ... per column]}.

The file is a regenerated cache (gitignored); a fresh clone produces it via this step.
Resumable: existing cache entries are kept and only missing jaspar_ids are fetched.
If the network is unavailable the step writes whatever it already has and exits 0, and
grn-allele-affinity degrades gracefully to overlap-only reporting.

Usage:
    backend/venv/bin/python backend/scripts/cache_motif_pwms.py
"""
import gzip
import json
import math
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
OUT_PATH = DATA_DIR / "motif_pwms.json.gz"
API = "https://jaspar.elixir.no/api/v1/matrix/{}/"

PSEUDO = 0.8
BG = 0.25
BASES = ("A", "C", "G", "T")


def pfm_to_lom(pfm: dict) -> list:
    """Convert a position frequency matrix to per-column log2 odds vectors [A,C,G,T]."""
    width = len(pfm["A"])
    lom = []
    for j in range(width):
        counts = [float(pfm[b][j]) for b in BASES]
        total = sum(counts) + 4 * PSEUDO
        col = [math.log2(((c + PSEUDO) / total) / BG) for c in counts]
        lom.append([round(v, 4) for v in col])
    return lom


def fetch_pfm(jaspar_id: str, timeout: int = 20):
    url = API.format(jaspar_id)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("pfm")


def main():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT motif_id, jaspar_id FROM motifs").fetchall()
    conn.close()

    # jaspar_id -> list of motif_ids that reference it
    by_jaspar = {}
    for motif_id, jaspar_id in rows:
        if jaspar_id:
            by_jaspar.setdefault(jaspar_id, []).append(motif_id)

    cache = {}
    if OUT_PATH.exists():
        cache = json.loads(gzip.open(OUT_PATH, "rt").read())
    have_jaspar = {v.get("jaspar_id") for v in cache.values()}

    todo = [j for j in by_jaspar if j not in have_jaspar]
    print(f"{len(by_jaspar)} distinct JASPAR matrices referenced; "
          f"{len(todo)} to fetch ({len(have_jaspar)} already cached)")

    fetched = failed = 0
    for i, jaspar_id in enumerate(sorted(todo), 1):
        try:
            pfm = fetch_pfm(jaspar_id)
            if not pfm:
                failed += 1
                continue
            lom = pfm_to_lom(pfm)
            for motif_id in by_jaspar[jaspar_id]:
                cache[motif_id] = {"jaspar_id": jaspar_id, "width": len(lom), "lom": lom}
            fetched += 1
        except urllib.error.HTTPError as e:
            # Retired/missing matrix (e.g. 404) — skip this one, keep going.
            print(f"  skip {jaspar_id}: HTTP {e.code}")
            failed += 1
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"  connection error on {jaspar_id}: {e}; writing partial cache and stopping")
            break
        except Exception as e:
            print(f"  skip {jaspar_id}: {e}")
            failed += 1
        if i % 50 == 0:
            print(f"  {i}/{len(todo)} fetched...")
            time.sleep(0.2)

    with gzip.open(OUT_PATH, "wt") as fh:
        json.dump(cache, fh)

    print(f"\nWrote {OUT_PATH}: {len(cache)} motif_id entries "
          f"({fetched} matrices fetched this run, {failed} failed)")
    if not cache:
        print("WARNING: no PWMs cached; allele-affinity will run in overlap-only mode.")


if __name__ == "__main__":
    main()
