"""Generic JASPAR-plant PWM motif scanner (config-driven) — replaces the per-species
scan_{tomato,petunia,arabidopsis}_motifs.py. Home of the PWM core (exact discretised
p-value DP, uniform 0.25 background) and the edge-driven scan.

For a species: map its TF regulators to JASPAR plant matrices (tf_motif_map_<species>.json
if present, else symbol/synonym), select the edges whose target promoters to scan
(species_config `scan_edge_sql`; None => all edges whose target is this species), scan
both strands, and write predicted binding sites (tier='JASPAR_scan') to
motifs_<species>.json + motif_hits_<species>.json.gz.

Needs the JASPAR plant PWMs at /tmp/jaspar_plants.jaspar and a genome FASTA for the
species (matching its gene_windows chromosome names via `chrom_norm`).

Usage: python backend/scripts/motif_scan.py <species> <genome.fa>
"""
import gzip
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import species_config  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
JASPAR = Path("/tmp/jaspar_plants.jaspar")

PVAL = 1e-4
BG = 0.25
PSEUDO = 0.8
SCALE = 100
BASE = {"A": 0, "C": 1, "G": 2, "T": 3}
COMP = str.maketrans("ACGTNacgtn", "TGCANtgcan")


# ---------- PWM core ----------
def score_pvalues(int_scores):
    dist = {0: 1.0}
    for pos in int_scores:
        nd = defaultdict(float)
        for s, p in dist.items():
            for base_score in pos:
                nd[s + int(base_score)] += p * BG
        dist = nd
    scores = sorted(dist, reverse=True)
    cum, pval_of, thr = 0.0, {}, None
    for s in scores:
        cum += dist[s]
        pval_of[s] = cum
        if thr is None and cum > PVAL:
            thr = s + 1
    if thr is None:
        thr = scores[-1]
    return thr, pval_of


def load_jaspar():
    entries, mid, name, rows = {}, None, None, []

    def finalize(mid, name, rows):
        counts = np.array(rows, dtype=float).T
        probs = (counts + PSEUDO) / (counts.sum(1, keepdims=True) + 4 * PSEUDO)
        lom = np.log2(probs / BG)
        ints = np.rint(lom * SCALE).astype(int)
        thr, pval_of = score_pvalues(ints)
        entries[mid] = (name, lom, ints, thr, pval_of)

    for line in JASPAR.read_text().splitlines():
        if line.startswith(">"):
            if mid and rows:
                finalize(mid, name, rows)
            parts = line[1:].split("\t")
            mid, name, rows = parts[0], (parts[1] if len(parts) > 1 else parts[0]), []
        elif line.strip():
            nums = re.findall(r"[\d.]+", line.split("[")[-1])
            rows.append([float(x) for x in nums])
    if mid and rows:
        finalize(mid, name, rows)
    return entries


def encode(seq):
    a = np.full(len(seq), -1, dtype=np.int8)
    for b, i in BASE.items():
        a[np.frombuffer(seq.encode(), dtype=np.uint8) == ord(b)] = i
    return a


def scan(seq_int, ints, thr, pval_of):
    L = ints.shape[0]
    n = seq_int.size - L + 1
    if n <= 0:
        return []
    score = np.zeros(n, dtype=np.int64)
    valid = np.ones(n, dtype=bool)
    for j in range(L):
        col = seq_int[j:j + n]
        valid &= col >= 0
        score += np.where(col >= 0, ints[j][np.clip(col, 0, 3)], 0)
    return [(int(i), int(score[i])) for i in np.where(valid & (score >= thr))[0]]


def _chrom_norm(style):
    if style == "tomato":
        def norm(name):
            m = re.search(r"ch0*(\d+)$", name)
            return m.group(1) if m else name
        return norm
    return lambda name: name


def main(species, fasta_path):
    cfg = species_config.get(species)
    if not cfg:
        sys.exit(f"unknown species '{species}'")
    assembly = cfg["assembly"]
    norm = _chrom_norm(cfg.get("chrom_norm", "identity"))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    jaspar = load_jaspar()
    name_to_mid = {}
    for mid, (nm, *_) in jaspar.items():
        for tok in re.split(r"[\/():]", nm):
            tok = tok.strip().upper()
            if tok:
                name_to_mid.setdefault(tok, mid)

    tf_mats, tf_symbol = defaultdict(set), {}
    seq_map = DATA_DIR / f"tf_motif_map_{species}.json"
    smap = json.loads(seq_map.read_text()) if seq_map.exists() else None
    for r in conn.execute("SELECT DISTINCT g.id, g.symbol, g.synonyms FROM genes g "
                          "JOIN interactions i ON i.source_id=g.id WHERE g.species=?", (species,)):
        if smap is not None:
            mats = set(smap.get(r["id"], []))
        else:
            cands = {(r["symbol"] or "").upper()}
            if r["synonyms"]:
                cands |= {s.upper() for s in r["synonyms"].split("; ")}
            mats = {name_to_mid[c] for c in cands if c in name_to_mid}
        if mats:
            tf_mats[r["id"]] = mats
            syns = r["synonyms"].split("; ") if r["synonyms"] else []
            tf_symbol[r["id"]] = syns[0] if syns else r["symbol"]
    print(f"{species} TFs mapped to a JASPAR motif: {len(tf_mats)}"
          + (" (sequence map)" if smap is not None else " (symbol match)"))

    atlas2ext = {r["atlas_gene_id"]: r["ext_gene_id"] for r in conn.execute(
        "SELECT atlas_gene_id, ext_gene_id FROM gene_id_crosswalk WHERE species=?", (species,))}
    prom = {r["ext_gene_id"]: r for r in conn.execute(
        "SELECT ext_gene_id, chromosome, start, end, strand FROM gene_windows "
        "WHERE window_type='promoter' AND assembly=?", (assembly,))}

    if cfg.get("scan_edge_sql"):
        edge_q = f"SELECT source_id, target_id FROM interactions WHERE {cfg['scan_edge_sql']}"
        edge_rows = conn.execute(edge_q)
    else:
        edge_rows = conn.execute("SELECT i.source_id, i.target_id FROM interactions i "
                                 "JOIN genes t ON t.id=i.target_id WHERE t.species=?", (species,))
    scan_jobs = defaultdict(set)
    for r in edge_rows:
        ext = atlas2ext.get(r["target_id"])
        if r["source_id"] in tf_mats and ext in prom:
            scan_jobs[ext].add(r["source_id"])
    print(f"target promoters to scan: {len(scan_jobs)}")

    by_chrom = defaultdict(list)
    for ext in scan_jobs:
        by_chrom[str(prom[ext]["chromosome"])].append(ext)
    want = set(by_chrom)
    seqs = {}

    def flush(name, chunks):
        if name is None:
            return
        cn = norm(name)
        if cn not in want:
            return
        s = "".join(chunks).upper()
        for ext in by_chrom[cn]:
            w = prom[ext]
            sub = s[w["start"]:w["end"]]
            if w["strand"] < 0:
                sub = sub.translate(COMP)[::-1]
            seqs[ext] = sub

    print(f"Reading {assembly} FASTA…")
    cur_name, cur = None, []
    with open(fasta_path) as fh:
        for line in fh:
            if line.startswith(">"):
                flush(cur_name, cur)
                cur_name, cur = line[1:].split()[0], []
            else:
                cur.append(line.strip())
    flush(cur_name, cur)
    print(f"promoter sequences extracted: {len(seqs)}")

    motifs_out, hits_out = {}, []
    for ext, tfs in scan_jobs.items():
        seq = seqs.get(ext)
        if not seq:
            continue
        si, si_rc = encode(seq), encode(seq.translate(COMP)[::-1])
        w = prom[ext]
        for tf in tfs:
            for mid in tf_mats[tf]:
                nm, lom, ints, thr, pval_of = jaspar[mid]
                L = ints.shape[0]
                syn_id = f"{mid}|{tf}"
                for strand, arr in ((1, si), (-1, si_rc)):
                    for off, sc in scan(arr, ints, thr, pval_of):
                        gs = w["start"] + off if strand == 1 else w["end"] - (off + L)
                        eff = (w["strand"] or 1) * strand
                        hits_out.append({
                            "ext_gene_id": ext, "motif_id": syn_id, "assembly": assembly,
                            "window_type": "promoter", "chromosome": str(w["chromosome"]),
                            "start": gs, "end": gs + L, "strand": 1 if eff >= 0 else -1,
                            "score": round(sc / SCALE, 3), "p_value": float(pval_of.get(sc, PVAL)),
                            "tier": "JASPAR_scan", "site_confidence": 0.5})
                        motifs_out[syn_id] = {"motif_id": syn_id, "source": "JASPAR2024",
                                              "jaspar_id": mid, "tf_gene_id": tf,
                                              "tf_symbol": tf_symbol.get(tf)}
    (DATA_DIR / f"motifs_{species}.json").write_text(json.dumps(list(motifs_out.values()), indent=1))
    with gzip.open(DATA_DIR / f"motif_hits_{species}.json.gz", "wt", encoding="utf-8") as f:
        json.dump(hits_out, f)
    print(f"Wrote motifs_{species}.json ({len(motifs_out)}) and "
          f"motif_hits_{species}.json.gz ({len(hits_out)} sites, p<{PVAL})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: motif_scan.py <species> <genome.fa>")
    main(sys.argv[1], sys.argv[2])
