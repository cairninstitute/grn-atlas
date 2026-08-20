#!/usr/bin/env python3
"""Build tobacco→petunia/tomato ortholog map via reciprocal best BLAST hits.

Tobacco (Nicotiana tabacum) isn't in PLAZA, so we construct orthologs by:
1. BLAST tobacco CDS against petunia/tomato CDS
2. BLAST petunia/tomato CDS against tobacco CDS
3. Keep reciprocal best hits (RBH) as high-confidence orthologs

Usage:
    python backend/scripts/build_tobacco_orthologs.py

Requires: NCBI BLAST+ (set BLAST_BIN env var or use default /tmp/blastwork/ncbi-blast-2.17.0+/bin)
"""
import gzip
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

BLAST_BIN = os.environ.get("BLAST_BIN", "/tmp/blastwork/ncbi-blast-2.17.0+/bin")
DATA_DIR = Path(__file__).parent.parent / "data"
WORK_DIR = Path("/tmp/blastwork")
TOBACCO_CDS_GZ = WORK_DIR / "tobacco_cds.fna.gz"

PEPPER_CDS_URL = ("https://ftp.psb.ugent.be/pub/plaza/plaza_public_dicots_04_5/Fasta/"
                   "cds.selected_transcript.can.fasta.gz")
PEPPER_CDS_GZ = DATA_DIR / "expr" / "can_cds.fasta.gz"

TARGETS = {
    "petunia": DATA_DIR / "expr" / "pax_cds.fa",
    "tomato": DATA_DIR / "expr" / "sly_cds.fasta.gz",
    "pepper": PEPPER_CDS_GZ,
}

EVALUE = 1e-10
MIN_IDENTITY = 60.0
MIN_COVERAGE = 0.5


def blast(tool):
    return str(Path(BLAST_BIN) / tool)


def prep_tobacco_cds():
    """Extract tobacco CDS, rename to LOC IDs, keep longest per gene."""
    out = WORK_DIR / "tobacco_cds_clean.fa"
    if out.exists():
        return out
    print("Preparing tobacco CDS...")
    seqs = {}
    cur_id, cur_seq = None, []
    with gzip.open(TOBACCO_CDS_GZ, "rt") as fin:
        for line in fin:
            if line.startswith(">"):
                if cur_id and cur_seq:
                    s = "".join(cur_seq)
                    if cur_id not in seqs or len(s) > len(seqs[cur_id]):
                        seqs[cur_id] = s
                m = re.search(r"\[gene=(LOC\d+)\]", line)
                cur_id = m.group(1) if m else None
                cur_seq = []
            else:
                cur_seq.append(line.strip())
        if cur_id and cur_seq:
            s = "".join(cur_seq)
            if cur_id not in seqs or len(s) > len(seqs[cur_id]):
                seqs[cur_id] = s
    with open(out, "w") as fout:
        for gid, seq in seqs.items():
            fout.write(f">{gid}\n{seq}\n")
    print(f"  {len(seqs):,} unique tobacco genes")
    return out


def prep_target_cds(species, path):
    """Ensure target CDS is uncompressed with clean headers (base gene ID)."""
    out = WORK_DIR / f"{species}_cds_clean.fa"
    if out.exists():
        return out
    print(f"Preparing {species} CDS...")
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as fin, open(out, "w") as fout:
        for line in fin:
            if line.startswith(">"):
                gene_id = line[1:].split()[0].rsplit(".", 1)[0]
                fout.write(f">{gene_id}\n")
            else:
                fout.write(line)
    return out


def make_db(fasta, name):
    db = WORK_DIR / name
    if (WORK_DIR / f"{name}.nsq").exists():
        return db
    print(f"Building BLAST DB: {name}")
    subprocess.run([blast("makeblastdb"), "-in", str(fasta), "-dbtype", "nucl",
                     "-out", str(db)], check=True,
                    capture_output=True)
    return db


def run_blast(query, db, out_file, num_threads=4):
    if out_file.exists():
        return
    print(f"Running BLAST: {query.name} vs {db.name}...")
    subprocess.run([
        blast("blastn"), "-query", str(query), "-db", str(db),
        "-out", str(out_file), "-outfmt", "6 qseqid sseqid pident length qlen slen evalue bitscore",
        "-evalue", str(EVALUE), "-max_target_seqs", "5",
        "-num_threads", str(num_threads),
    ], check=True)


def parse_blast_hits(blast_file):
    """Parse BLAST output, return dict of query -> best hit (by bitscore)."""
    best = {}
    with open(blast_file) as f:
        for line in f:
            parts = line.strip().split("\t")
            qid, sid = parts[0], parts[1]
            pident, alen = float(parts[2]), int(parts[3])
            qlen, slen = int(parts[4]), int(parts[5])
            bitscore = float(parts[7])

            if pident < MIN_IDENTITY:
                continue
            cov = alen / min(qlen, slen)
            if cov < MIN_COVERAGE:
                continue

            if qid not in best or bitscore > best[qid][1]:
                best[qid] = (sid, bitscore, pident, cov)
    return best


def find_rbh(forward_hits, reverse_hits):
    """Find reciprocal best hits."""
    rbh = {}
    for qid, (sid, score, pident, cov) in forward_hits.items():
        if sid in reverse_hits and reverse_hits[sid][0] == qid:
            rbh[qid] = {"target": sid, "identity": pident, "coverage": cov,
                         "score": score}
    return rbh


def main():
    makeblastdb = blast("makeblastdb")
    if not Path(makeblastdb).exists():
        import shutil
        if not shutil.which("makeblastdb"):
            print("BLAST+ not found — skipping tobacco ortholog build.")
            print(f"  Set BLAST_BIN env var or install BLAST+ to enable.")
            sys.exit(0)
    WORK_DIR.mkdir(exist_ok=True)

    if not PEPPER_CDS_GZ.exists():
        PEPPER_CDS_GZ.parent.mkdir(parents=True, exist_ok=True)
        print("Downloading pepper CDS from PLAZA...")
        import urllib.request
        urllib.request.urlretrieve(PEPPER_CDS_URL, PEPPER_CDS_GZ)
        print(f"  -> {PEPPER_CDS_GZ} ({PEPPER_CDS_GZ.stat().st_size:,} bytes)")

    tobacco_fa = prep_tobacco_cds()
    tobacco_db = make_db(tobacco_fa, "tobacco_db")

    # Get unique tobacco gene IDs from regulation file
    tobacco_genes = set()
    with open(DATA_DIR / "regulation_tobacco_raw.tsv") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                tobacco_genes.add(parts[0])
                tobacco_genes.add(parts[2])
    print(f"Tobacco genes in regulation data: {len(tobacco_genes):,}")

    all_orthologs = []

    for species, cds_path in TARGETS.items():
        print(f"\n=== {species.upper()} ===")
        target_fa = prep_target_cds(species, cds_path)
        target_db = make_db(target_fa, f"{species}_db")

        fwd_file = WORK_DIR / f"tobacco_vs_{species}.blast"
        rev_file = WORK_DIR / f"{species}_vs_tobacco.blast"

        run_blast(tobacco_fa, target_db, fwd_file)
        run_blast(target_fa, tobacco_db, rev_file)

        fwd_hits = parse_blast_hits(fwd_file)
        rev_hits = parse_blast_hits(rev_file)
        rbh = find_rbh(fwd_hits, rev_hits)

        relevant = {k: v for k, v in rbh.items() if k in tobacco_genes}
        print(f"  Total RBH pairs: {len(rbh):,}")
        print(f"  RBH pairs involving regulation genes: {len(relevant):,}")
        print(f"  Mean identity: {sum(v['identity'] for v in rbh.values())/max(len(rbh),1):.1f}%")

        for tob_id, info in rbh.items():
            all_orthologs.append({
                "gene_a": tob_id, "species_a": "tobacco",
                "gene_b": info["target"], "species_b": species,
                "rel_type": "blast_rbh",
                "identity": round(info["identity"], 1),
                "coverage": round(info["coverage"], 3),
                "score": info["score"],
            })

    out_path = DATA_DIR / "orthologs_tobacco_blast.json"
    with open(out_path, "w") as f:
        json.dump(all_orthologs, f, indent=1)
    print(f"\nWrote {len(all_orthologs):,} ortholog pairs to {out_path}")


if __name__ == "__main__":
    main()
