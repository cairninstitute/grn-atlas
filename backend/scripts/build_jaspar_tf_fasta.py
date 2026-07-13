"""
Build a FASTA of the TF protein behind each JASPAR plant matrix (header =
matrix_id), for sequence-based TF<->motif assignment. One-time, species-agnostic.

  1. JASPAR REST: matrix_id -> uniprot_ids  (per-matrix, threaded)
  2. UniProt: accession -> protein sequence (batched)

Output: /tmp/blastwork/jaspar_tf.fasta   (not committed; a BLAST input)

Usage: python backend/scripts/build_jaspar_tf_fasta.py [jaspar_plants.jaspar]
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

JASPAR_FILE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/jaspar_plants.jaspar")
OUT = Path("/tmp/blastwork/jaspar_tf.fasta")
UA = {"User-Agent": "grn-atlas-build/1.0"}


def get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())


def matrix_uniprot(mid):
    try:
        d = get(f"https://jaspar.elixir.no/api/v1/matrix/{mid}/")
        ups = d.get("uniprot_ids") or []
        return mid, (ups[0] if ups else None)
    except Exception:
        return mid, None


def main():
    mids = [ln[1:].split("\t")[0] for ln in JASPAR_FILE.read_text().splitlines() if ln.startswith(">")]
    print(f"matrices: {len(mids)}")
    with ThreadPoolExecutor(max_workers=12) as pool:
        pairs = list(pool.map(matrix_uniprot, mids))
    mid_up = {m: u for m, u in pairs if u}
    print(f"matrices with a UniProt id: {len(mid_up)}")

    accs = sorted(set(mid_up.values()))
    seqs = {}
    for i in range(0, len(accs), 40):
        chunk = accs[i:i + 40]
        q = "(" + " OR ".join(f"accession:{a}" for a in chunk) + ")"
        url = ("https://rest.uniprot.org/uniprotkb/search?format=fasta&size=500&query="
               + urllib.parse.quote(q))
        try:
            fa = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read().decode()
        except Exception as e:
            print(f"  batch {i // 40} failed: {e}")
            continue
        acc = None
        for line in fa.splitlines():
            if line.startswith(">"):
                m = re.search(r"\|([A-Z0-9]+)\|", line)
                acc = m.group(1) if m else None
                if acc:
                    seqs[acc] = []
            elif acc:
                seqs[acc].append(line)
    seqs = {a: "".join(v) for a, v in seqs.items() if v}
    print(f"UniProt sequences fetched: {len(seqs)}")

    OUT.parent.mkdir(exist_ok=True)
    n = 0
    with open(OUT, "w") as fh:
        for mid, up in mid_up.items():
            if up in seqs:
                fh.write(f">{mid}\n{seqs[up]}\n")
                n += 1
    print(f"Wrote {OUT} ({n} matrix TF proteins)")


if __name__ == "__main__":
    main()
