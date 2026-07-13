"""
BLAST-based identification of petunia (and other) master regulators that
functional descriptions don't cleanly label — e.g. the anthocyanin MBW complex
(AN2/AN1/AN11/JAF13/PH4/DPL). Produces regulator_map.json, which build_db uses
to assign these genes a real symbol (a measured sequence identity, not an
inferred synonym).

Pipeline:
  1. Fetch characterized regulator protein sequences from UniProt (curated list).
  2. blastp them against the species proteome (PLAZA proteome FASTA).
  3. Best hit per reference, filtered by %identity/coverage -> gene_id -> symbol.

Toolchain (one-time): NCBI BLAST+ (blastp, makeblastdb). Point BLAST_BIN at the
bin dir, or have them on PATH:
  curl -sL https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/ \\
    ncbi-blast-2.17.0+-x64-linux.tar.gz | tar xz
  export BLAST_BIN=$PWD/ncbi-blast-2.17.0+/bin

Usage: python backend/scripts/blast_regulators.py <proteome.fasta> [workdir]
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
BLAST_BIN = os.environ.get("BLAST_BIN", "")
UA = {"User-Agent": "grn-atlas-build/1.0"}
MIN_IDENTITY, MIN_COVERAGE = 35.0, 50.0

# label -> (canonical symbol, description, UniProt query, priority).
# Petunia-specific identities outrank Arabidopsis-derived ones for the same gene.
REFERENCES = [
    ("PhAN2",  "AN2",       "anthocyanin master MYB",        "gene:AN2 AND taxonomy_id:4102", 3),
    ("PhAN1",  "AN1",       "anthocyanin bHLH",              "gene:AN1 AND taxonomy_id:4102", 3),
    ("PhAN11", "AN11",      "anthocyanin WD40",              "gene:AN11 AND taxonomy_id:4102", 3),
    ("PhJAF13","JAF13",     "anthocyanin bHLH",              "gene:JAF13 AND taxonomy_id:4102", 3),
    ("PhPH4",  "PH4",       "vacuolar-pH / anthocyanin MYB", "gene:PH4 AND taxonomy_id:4102", 3),
    ("PhDPL",  "DPL",       "anthocyanin MYB (DEEP PURPLE)", "gene:DPL AND taxonomy_id:4102", 3),
    ("AtPAP1", "PAP1-like", "PAP1-like anthocyanin MYB",     "gene:PAP1 AND organism_id:3702", 1),
    ("AtMYB12","MYB12",     "flavonol MYB",                  "gene:MYB12 AND organism_id:3702", 1),
    ("AtTT2",  "TT2-like",  "proanthocyanidin MYB",          "gene:TT2 AND organism_id:3702", 1),
    ("AtAG",   "AG",        "AGAMOUS C-class MADS",          "gene:AG AND organism_id:3702", 2),
    ("AtAP3",  "AP3",       "APETALA3 B-class MADS",         "gene:AP3 AND organism_id:3702", 2),
    ("AtPI",   "PI",        "PISTILLATA B-class MADS",       "gene:PI AND organism_id:3702", 2),
    ("SlANT1", "ANT1",      "tomato anthocyanin MYB",        "gene:ANT1 AND organism_id:4081", 3),
]


def uniprot_fasta(query):
    for q in (query + " AND reviewed:true", query):
        url = ("https://rest.uniprot.org/uniprotkb/search?query="
               + urllib.parse.quote(q) + "&format=fasta&size=1")
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
        if data.strip():
            return data.decode()
    return ""


def bin_path(tool):
    return str(Path(BLAST_BIN) / tool) if BLAST_BIN else tool


def protein_to_gene_id(protein_id):
    """Proteome protein id -> atlas gene id (drop the transcript suffix only):
    Solyc10g086260.2.1 -> Solyc10g086260.2 ; Peaxi162Scf00000g00013.1 -> Peaxi162Scf00000g00013"""
    return protein_id.rsplit(".", 1)[0]


def main(proteome, out_json, workdir="/tmp/blastwork"):
    out_json = Path(out_json)
    wd = Path(workdir); wd.mkdir(exist_ok=True)
    ref = wd / "reference.fasta"
    meta = {label: (sym, desc, prio) for label, sym, desc, _, prio in REFERENCES}
    with open(ref, "w") as fh:
        for label, sym, desc, query, prio in REFERENCES:
            fa = uniprot_fasta(query)
            if fa:
                fh.write(f">{label}\n" + "".join(fa.splitlines()[1:]) + "\n")
            print(f"  {label:8} {'ok' if fa else 'NOT FOUND'}")

    subprocess.run([bin_path("makeblastdb"), "-in", proteome, "-dbtype", "prot",
                    "-out", str(wd / "db")], check=True, stdout=subprocess.DEVNULL)
    out = subprocess.run(
        [bin_path("blastp"), "-query", str(ref), "-db", str(wd / "db"),
         "-evalue", "1e-10", "-max_target_seqs", "3", "-num_threads", "4",
         "-outfmt", "6 qseqid sseqid pident length evalue bitscore qcovs"],
        check=True, capture_output=True, text=True).stdout

    best = {}
    for line in out.splitlines():
        q, s, pid, ln, ev, bit, qcov = line.split("\t")
        pid, qcov, bit = float(pid), float(qcov), float(bit)
        if pid < MIN_IDENTITY or qcov < MIN_COVERAGE:
            continue
        gene = protein_to_gene_id(s)
        if q not in best or bit > best[q][1]:
            best[q] = (gene, bit, pid)

    pick = {}
    for q, (gene, bit, pid) in best.items():
        sym, desc, prio = meta[q]
        cand = (prio, sym, desc, round(pid))
        if gene not in pick or cand[0] > pick[gene][0]:
            pick[gene] = cand
    rows = [{"gene_id": g, "name": sym, "description": desc,
             "pct_identity": pid, "source": "BLAST_curated"}
            for g, (prio, sym, desc, pid) in sorted(pick.items())]
    out_json.write_text(json.dumps(rows, indent=1))
    print(f"Wrote {out_json} ({len(rows)} curated regulators)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "/tmp/blastwork")
