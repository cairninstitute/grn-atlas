"""
Sequence-based TF<->motif assignment (upgrade over symbol matching).

For each edge-source TF in a species, BLAST its protein against the JASPAR plant
matrices' TF proteins (built by build_jaspar_tf_fasta.py) and assign the motif of
its best match. Merged with the existing symbol/synonym matches (symbol wins on
overlap). Raises scan coverage past the ~62-64% symbol-only ceiling.

Output: tf_motif_map_<species>.json  = { tf_gene_id: [matrix_id, ...] }
The scanners load this if present, else fall back to symbol matching.

Requires: /tmp/blastwork/jaspar_tf.fasta and BLAST+ (BLAST_BIN or on PATH).

Usage: python backend/scripts/map_tf_motifs.py <species> <proteome.fasta>
"""
import json
import os
import re
import subprocess
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
JASPAR_TF = Path("/tmp/blastwork/jaspar_tf.fasta")
WD = Path("/tmp/blastwork")
BLAST_BIN = os.environ.get("BLAST_BIN", "/tmp/blastwork/ncbi-blast-2.17.0+/bin")
MIN_IDENTITY, MAX_EVALUE, MIN_COV = 30.0, 1e-5, 40.0


def binp(t):
    return str(Path(BLAST_BIN) / t) if BLAST_BIN else t


def jaspar_names():
    names = {}
    for ln in Path("/tmp/jaspar_plants.jaspar").read_text().splitlines():
        if ln.startswith(">"):
            mid, nm = ln[1:].split("\t")[0], ln[1:].split("\t")[1].strip()
            for tok in re.split(r"[\/():]", nm):
                tok = tok.strip().upper()
                if tok:
                    names.setdefault(tok, mid)
    return names


def main(species, proteome):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    tfs = {}
    for r in conn.execute("""SELECT DISTINCT g.id, g.symbol, g.synonyms FROM genes g
                             JOIN interactions i ON i.source_id=g.id WHERE g.species=?""", (species,)):
        tfs[r["id"]] = r
    print(f"{species} edge-source TFs: {len(tfs)}")

    # symbol/synonym matches (existing behaviour)
    names = jaspar_names()
    mapping = defaultdict(set)
    for gid, r in tfs.items():
        cands = {(r["symbol"] or "").upper()}
        if r["synonyms"]:
            cands |= {s.upper() for s in r["synonyms"].split("; ")}
        for c in cands:
            if c in names:
                mapping[gid].add(names[c])
    n_symbol = sum(1 for g in mapping if mapping[g])

    # extract regulator protein sequences from the proteome (atlas id after "|")
    want = set(tfs)
    seqs, cur_id, cur = {}, None, []
    with open(proteome) as fh:
        for line in fh:
            if line.startswith(">"):
                if cur_id in want:
                    seqs[cur_id] = "".join(cur)
                parts = line[1:].split("|")
                cur_id = parts[1].strip() if len(parts) > 1 else parts[0].split()[0]
                cur = []
            else:
                cur.append(line.strip())
        if cur_id in want:
            seqs[cur_id] = "".join(cur)
    q_fa = WD / f"reg_{species}.fasta"
    with open(q_fa, "w") as fh:
        for gid, s in seqs.items():
            fh.write(f">{gid}\n{s}\n")
    print(f"regulator proteins extracted: {len(seqs)}")

    # blast regulators vs JASPAR TF proteins
    subprocess.run([binp("makeblastdb"), "-in", str(JASPAR_TF), "-dbtype", "prot",
                    "-out", str(WD / "jaspardb")], check=True, stdout=subprocess.DEVNULL)
    out = subprocess.run(
        [binp("blastp"), "-query", str(q_fa), "-db", str(WD / "jaspardb"),
         "-evalue", str(MAX_EVALUE), "-max_target_seqs", "1", "-num_threads", "4",
         "-outfmt", "6 qseqid sseqid pident evalue bitscore qcovs"],
        check=True, capture_output=True, text=True).stdout

    best = {}
    for line in out.splitlines():
        q, s, pid, ev, bit, qcov = line.split("\t")
        pid, qcov, bit = float(pid), float(qcov), float(bit)
        if pid < MIN_IDENTITY or qcov < MIN_COV:
            continue
        if q not in best or bit > best[q][1]:
            best[q] = (s, bit)
    n_seq_new = 0
    for gid, (mid, _) in best.items():
        if not mapping[gid]:
            n_seq_new += 1
        mapping[gid].add(mid)

    out_map = {g: sorted(m) for g, m in mapping.items() if m}
    (DATA_DIR / f"tf_motif_map_{species}.json").write_text(json.dumps(out_map, indent=1))
    print(f"  symbol-matched TFs: {n_symbol}; +sequence-only TFs: {n_seq_new}; "
          f"total mapped: {len(out_map)}/{len(tfs)}")
    print(f"Wrote tf_motif_map_{species}.json")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
