"""
Load Arabidopsis DAP-seq binding peaks (O'Malley et al., Cell 2016; Plant Cistrome DB).

Source: GEO GSE60143 (GSE60143_RAW.tar) — per-TF GEM narrowPeak files. This is the exact
assay behind the atlas's DAP-seq *edges* (PMID 27203113); here we ingest the genome-wide
*peak coordinates* so the chromatin/cis-regulatory skills have real data:

  - chromatin_peaks   : each DAP-seq binding peak (chrom/start/end/summit/score)
  - peak_gene_links   : peak -> gene whose promoter window it overlaps (measured link)
  - cis_support_edges : TF -> target "DAP-seq_peak" support (the peak's TF binds the target
                        promoter) — a measured cis layer for grn-cis-support-audit
  - peak_motif_hits   : peak -> its DAP-seq TF (so enhancer-network can name the regulator),
                        added only when that TF has a JASPAR motif row to join against

Each narrowPeak file is one TF (its atlas gene id is in the filename); maize/other-species
constructs without an Arabidopsis gene id are skipped. Peaks are capped per TF by score to
keep the layer bounded; the cap is reported, not hidden.

Idempotent: clears this dataset's rows first. Skips gracefully if the archive is absent.

Usage:
    # one-time download (74 MB):
    curl -L -o /tmp/GSE60143_RAW.tar \\
      https://ftp.ncbi.nlm.nih.gov/geo/series/GSE60nnn/GSE60143/suppl/GSE60143_RAW.tar
    backend/venv/bin/python backend/scripts/load_dapseq_peaks.py [/tmp/GSE60143_RAW.tar]
"""
import gzip
import re
import sqlite3
import sys
import tarfile
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
DEFAULT_TAR = Path("/tmp/GSE60143_RAW.tar")
DATASET_ID = "PlantCistrome_GSE60143"
SUPPORT_TYPE = "DAP-seq_peak"
ATID_RE = re.compile(r"(AT[1-5CM]G\d{5})", re.IGNORECASE)
# The TF construct token sits right before the _col / _colamp genotype marker.
TOKEN_RE = re.compile(r"-([A-Za-z0-9.]+)_(?:col|colamp)", re.IGNORECASE)
MAX_PEAKS_PER_TF = 500


def norm_chrom(c):
    c = c.strip()
    if c.lower().startswith("chr"):
        return "Chr" + c[3:]
    return "Chr" + c


def load_promoter_index(conn):
    """chrom -> (sorted window starts, [(start,end,gene_id)...]) for overlap queries."""
    by_chrom = defaultdict(list)
    for gid, chrom, start, end in conn.execute(
        "SELECT ext_gene_id, chromosome, start, end FROM gene_windows "
        "WHERE window_type='promoter' AND ext_gene_id LIKE 'AT%'"
    ):
        by_chrom[chrom].append((start, end, gid))
    index = {}
    for chrom, wins in by_chrom.items():
        wins.sort()
        index[chrom] = ([w[0] for w in wins], wins)
    return index


def overlapping_genes(index, chrom, start, end):
    if chrom not in index:
        return []
    starts, wins = index[chrom]
    # windows whose start <= end; scan left from that point while window.end >= start.
    hi = bisect_right(starts, end)
    out = []
    for i in range(hi - 1, -1, -1):
        w_start, w_end, gid = wins[i]
        if w_end >= start:
            out.append(gid)
        if w_start < start - 20000:  # promoter windows are short; stop scanning far-left
            break
    return out


def build_tf_resolver(conn):
    """Map a DAP-seq filename TF token (AT id or symbol/alias) -> atlas Arabidopsis gene id."""
    atlas = {r[0] for r in conn.execute("SELECT id FROM genes WHERE species='arabidopsis'")}
    sym = {}
    for gid, s in conn.execute(
            "SELECT id, symbol FROM genes WHERE species='arabidopsis' AND symbol IS NOT NULL"):
        sym.setdefault(s.upper(), gid)
    for gid, a in conn.execute(
            "SELECT g.id, ga.alias FROM gene_aliases ga JOIN genes g ON g.id = ga.gene_id "
            "WHERE g.species='arabidopsis'"):
        sym.setdefault(a.upper(), gid)

    def resolve(filename):
        m = ATID_RE.search(filename)
        if m and m.group(1).upper() in atlas:
            return m.group(1).upper()
        t = TOKEN_RE.search(filename)
        if t:
            tok = t.group(1).upper()
            if tok in atlas:
                return tok
            return sym.get(tok)
        return None

    return resolve


def iter_peak_files(tar_path: Path, resolve):
    with tarfile.open(tar_path, "r") as tar:
        for member in tar.getmembers():
            if not member.name.endswith(".narrowPeak.gz") or "DAPSeq" not in member.name:
                continue
            tf = resolve(member.name)
            if not tf:
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            yield tf, gzip.decompress(fh.read()).decode("utf-8", "replace")


def main():
    tar_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TAR
    if not tar_path.exists():
        print(f"DAP-seq archive not found at {tar_path} — skipping (optional heavy layer).")
        print("  Download: curl -L -o /tmp/GSE60143_RAW.tar "
              "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE60nnn/GSE60143/suppl/GSE60143_RAW.tar")
        return

    conn = sqlite3.connect(DB_PATH)
    resolve = build_tf_resolver(conn)
    prom_index = load_promoter_index(conn)
    # TFs that have a JASPAR motif row (so peak_motif_hits can join to `motifs`).
    tf_motif = {}
    for mid, tf in conn.execute("SELECT motif_id, tf_gene_id FROM motifs WHERE tf_gene_id IS NOT NULL"):
        tf_motif.setdefault(tf, mid)

    # Clear prior rows for this dataset.
    conn.execute("DELETE FROM chromatin_peaks WHERE dataset_id = ?", (DATASET_ID,))
    conn.execute("DELETE FROM peak_gene_links WHERE dataset_id = ?", (DATASET_ID,))
    conn.execute("DELETE FROM cis_support_edges WHERE support_type = ?", (SUPPORT_TYPE,))
    conn.execute("DELETE FROM peak_motif_hits WHERE peak_id LIKE 'DAP\\_%' ESCAPE '\\'")
    conn.commit()

    # Aggregate peaks per TF across its replicate files, then cap by score.
    peaks_by_tf = defaultdict(list)
    files = tfs_seen = 0
    for tf, text in iter_peak_files(tar_path, resolve):
        files += 1
        for line in text.splitlines():
            f = line.split("\t")
            if len(f) < 5:
                continue
            try:
                chrom = norm_chrom(f[0]); start = int(f[1]); end = int(f[2]); score = float(f[4])
            except ValueError:
                continue
            summit = start
            if ":" in f[3]:
                try:
                    summit = int(f[3].split(":")[1])
                except ValueError:
                    pass
            peaks_by_tf[tf].append((score, chrom, start, end, summit))

    peak_rows, link_rows, cis_rows, motif_rows = [], [], [], []
    seen_cis = set()
    for tf, plist in peaks_by_tf.items():
        tfs_seen += 1
        plist.sort(reverse=True)  # strongest first
        for score, chrom, start, end, summit in plist[:MAX_PEAKS_PER_TF]:
            peak_id = f"DAP_{tf}_{chrom}_{start}"
            peak_rows.append((peak_id, "arabidopsis", chrom, start, end, summit, score,
                              "DAP-seq", DATASET_ID))
            link_score = min(1.0, score / 1000.0)
            for gid in overlapping_genes(prom_index, chrom, start, end):
                link_rows.append((peak_id, gid, link_score, "promoter_overlap", 0,
                                  "arabidopsis", DATASET_ID))
                key = (tf, gid)
                if key not in seen_cis:
                    seen_cis.add(key)
                    cis_rows.append((tf, gid, peak_id, SUPPORT_TYPE, link_score, "arabidopsis"))
            if tf in tf_motif:
                motif_rows.append((peak_id, tf_motif[tf], tf, score, None, summit, "."))

    conn.executemany("INSERT OR REPLACE INTO chromatin_peaks "
                     "(peak_id,species,chrom,start_pos,end_pos,summit,score,peak_type,dataset_id) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", peak_rows)
    conn.executemany("INSERT OR REPLACE INTO peak_gene_links "
                     "(peak_id,gene_id,link_score,link_type,distance_bp,species,dataset_id) "
                     "VALUES (?,?,?,?,?,?,?)", link_rows)
    conn.executemany("INSERT INTO cis_support_edges "
                     "(source_id,target_id,peak_id,support_type,score,species) VALUES (?,?,?,?,?,?)",
                     cis_rows)
    if motif_rows:
        conn.executemany("INSERT OR IGNORE INTO peak_motif_hits "
                         "(peak_id,motif_id,tf_gene_id,score,pvalue,position,strand) "
                         "VALUES (?,?,?,?,?,?,?)", motif_rows)
    conn.commit()
    conn.close()

    print(f"DAP-seq peaks loaded from {files} files / {tfs_seen} Arabidopsis TFs (cap {MAX_PEAKS_PER_TF}/TF)")
    print(f"  chromatin_peaks:    {len(peak_rows):,}")
    print(f"  peak_gene_links:    {len(link_rows):,}")
    print(f"  cis_support_edges:  {len(cis_rows):,}  (measured TF->target DAP-seq support)")
    print(f"  peak_motif_hits:    {len(motif_rows):,}")


if __name__ == "__main__":
    main()
