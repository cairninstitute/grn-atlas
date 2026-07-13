"""Fetch REAL, curated gene symbols for plant loci (replaces inferred ortholog names).

Sources (authoritative, honest):
  tomato  : UniProt Swiss-Prot (reviewed) entries whose EnsemblPlants xref is a Solyc id
            -> direct, high-confidence mapping to our atlas ids.  source = "UniProt"
  petunia : UniProt Swiss-Prot (reviewed) *Petunia hybrida* proteins with a gene name,
            tblastn-mapped to the P. axillaris (Peaxi162) CDS by strong homology
            (>=90% identity). Real petunia gene names (AN2, DFR, CHS, PH…) attached to
            the axillaris locus by sequence.  source = "UniProt:homology"

Output: backend/data/curated_symbols_<species>.json
  { atlas_gene_id: {"symbol": str, "source": str, "identity": float|null} }

Usage: python backend/scripts/fetch_curated_symbols.py <tomato|petunia>
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
UA = {"User-Agent": "grn-atlas-build/1.0"}
BLAST_BIN = os.environ.get("BLAST_BIN", "/tmp/blastwork/ncbi-blast-2.17.0+/bin")


def _uniprot_stream(query, fields):
    url = (f"https://rest.uniprot.org/uniprotkb/stream?query={query}"
           f"&fields={fields}&format=tsv")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        return [ln.split("\t") for ln in r.read().decode().splitlines()][1:]


def tomato():
    rows = _uniprot_stream("organism_id:4081+AND+reviewed:true", "gene_primary,xref_ensemblplants")
    base2sym = {}
    for r in rows:
        sym = (r[0] or "").strip()
        ens = (r[1] or "").strip() if len(r) > 1 else ""
        if not sym or not ens:
            continue
        for e in ens.split(";"):
            m = re.match(r"(Solyc\d+g\d+)", e.strip())
            if m:
                base2sym.setdefault(m.group(1), sym)
    # map base Solyc id -> our full atlas id
    import sqlite3
    c = sqlite3.connect(DATA / "grn.sqlite3")
    out = {}
    for (gid,) in c.execute("SELECT id FROM genes WHERE species='tomato'"):
        b = gid.rsplit(".", 1)[0]
        if b in base2sym:
            out[gid] = {"symbol": base2sym[b], "source": "UniProt", "identity": None}
    _write("tomato", out)


def petunia():
    # 1. UniProt P. hybrida reviewed proteins WITH a gene name -> FASTA
    rows = _uniprot_stream("organism_id:4102+AND+reviewed:true", "gene_primary,sequence")
    fa = DATA / "expr" / "uniprot_phyb.faa"
    n = 0
    with open(fa, "w") as f:
        for r in rows:
            sym = (r[0] or "").strip()
            seq = (r[1] or "").strip() if len(r) > 1 else ""
            if sym and seq:
                f.write(f">{sym.upper()}\n{seq}\n")
                n += 1
    print(f"UniProt P. hybrida proteins with a gene name: {n}", flush=True)

    # 2. petunia CDS blast db
    cds_gz = DATA / "transcripts_petunia.fasta.gz"
    cds = DATA / "expr" / "pax_cds.fa"
    subprocess.run(["bash", "-c", f"zcat '{cds_gz}' > '{cds}'"], check=True)
    db = DATA / "expr" / "pax_cds_blastdb"
    subprocess.run([f"{BLAST_BIN}/makeblastdb", "-in", str(cds), "-dbtype", "nucl",
                    "-out", str(db)], check=True, capture_output=True)

    # 3. tblastn proteins vs CDS
    out6 = DATA / "expr" / "phyb_vs_pax.tsv"
    subprocess.run([f"{BLAST_BIN}/tblastn", "-query", str(fa), "-db", str(db),
                    "-evalue", "1e-20", "-max_target_seqs", "3", "-num_threads", "4",
                    "-outfmt", "6 qseqid sseqid pident evalue bitscore qcovhsp",
                    "-out", str(out6)], check=True)

    # 4. best hit per query with strict thresholds -> symbol per gene
    best_for_gene = {}   # gene -> (bitscore, symbol, identity)
    for ln in open(out6):
        q, s, pid, ev, bits, qcov = ln.rstrip("\n").split("\t")
        pid, bits, qcov = float(pid), float(bits), float(qcov)
        if pid < 90.0 or qcov < 70.0:
            continue
        gene = s.rsplit(".", 1)[0]     # transcript -> gene id
        cur = best_for_gene.get(gene)
        if cur is None or bits > cur[0]:
            best_for_gene[gene] = (bits, q, pid)
    out = {g: {"symbol": sym, "source": "UniProt:homology", "identity": round(pid, 1)}
           for g, (bits, sym, pid) in best_for_gene.items()}
    _write("petunia", out)


def _write(species, out):
    path = DATA / f"curated_symbols_{species}.json"
    path.write_text(json.dumps(out, indent=0))
    print(f"wrote {path}  ({len(out)} curated symbols)", flush=True)


if __name__ == "__main__":
    sp = sys.argv[1] if len(sys.argv) > 1 else ""
    if sp == "tomato":
        tomato()
    elif sp == "petunia":
        petunia()
    else:
        sys.exit("usage: fetch_curated_symbols.py <tomato|petunia>")
