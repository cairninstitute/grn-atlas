"""
Tomato sequence-context ingestion (Path B) — REAL windows + crosswalk.

Builds two of the four sequence-context caches from the SL4.0 / ITAG4.1 gene
models, which is everything derivable from coordinates alone (no FASTA needed):

  - gene_id_crosswalk.json : atlas ITAG2.4 id  <->  ITAG4.1 id  (base-id match)
  - gene_windows.json      : promoter (TSS -upstream/+downstream) and gene_body
                             windows on SL4.0, BED 0-based half-open

NOT produced here: motifs.json / motif_hits.json. Those require a FIMO/MEME scan
of JASPAR + PlantRegMap PWMs over a genome FASTA (and ATAC peak processing),
which is a separate compute job with tools not assumed present. They drop into
the same tables when delivered; this script deliberately does not fabricate them.

Usage: python backend/scripts/fetch_tomato_seqctx.py
"""
import gzip
import json
import re
import sqlite3
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
CROSSWALK_JSON = DATA_DIR / "gene_id_crosswalk.json.gz"
WINDOWS_JSON = DATA_DIR / "gene_windows.json.gz"

ITAG41_GFF = ("https://solgenomics.net/ftp/genomes/Solanum_lycopersicum/"
              "annotation/ITAG4.1_release/ITAG4.1_gene_models.gff")
ASSEMBLY = "SL4.0"
PROMOTER_UP = 2000     # bp upstream of TSS (transcription direction)
PROMOTER_DOWN = 500    # bp downstream of TSS
UA = {"User-Agent": "Mozilla/5.0 (grn-atlas-build)"}


def base_id(gene_id):
    """Solyc01g005060.2 / Solyc01g005060.1 -> Solyc01g005060."""
    return gene_id.split(".")[0]


def norm_chrom(name):
    """SL4.0ch07 -> '7'; SL4.0ch00 -> '0'."""
    m = re.search(r"ch0*(\d+)$", name)
    return m.group(1) if m else name


def load_atlas_tomato():
    conn = sqlite3.connect(DB_PATH)
    ids = [r[0] for r in conn.execute("SELECT id FROM genes WHERE species='tomato'")]
    conn.close()
    return {base_id(i): i for i in ids}


def promoter_window(start, end, strand):
    """BED0 half-open promoter window, strand-aware, from 1-based GFF coords.
    Plus:  TSS = gene start (0-based start-1); window [TSS-UP, TSS+DOWN).
    Minus: TSS = gene end;                     window [end-DOWN, end+UP)."""
    if strand >= 0:
        tss0 = start - 1
        return max(0, tss0 - PROMOTER_UP), tss0 + PROMOTER_DOWN
    return max(0, end - PROMOTER_DOWN), end + PROMOTER_UP


def main():
    atlas = load_atlas_tomato()
    print(f"Atlas tomato genes: {len(atlas)}")
    print("Downloading ITAG4.1 gene models…")
    req = urllib.request.Request(ITAG41_GFF, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as resp:
        text = resp.read().decode("utf-8", "replace")

    crosswalk, windows = [], []
    seen_base = set()
    n_genes = matched = 0
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        c = line.split("\t")
        if len(c) != 9 or c[2] != "gene":
            continue
        n_genes += 1
        m = re.search(r"ID=(?:gene:)?([^;]+)", c[8])
        if not m:
            continue
        ext_id = m.group(1)
        base = base_id(ext_id)
        atlas_id = atlas.get(base)
        if not atlas_id:
            continue  # ITAG4.1-only gene (new model) — not in the atlas graph
        matched += 1
        # split relation if the same base appears more than once in ITAG4.1
        relation = "split" if base in seen_base else "1:1"
        seen_base.add(base)
        crosswalk.append({
            "species": "tomato", "atlas_gene_id": atlas_id, "ext_gene_id": ext_id,
            "ext_assembly": ASSEMBLY, "relation": relation,
        })
        chrom = norm_chrom(c[0])
        start, end = int(c[3]), int(c[4])
        strand = 1 if c[6] == "+" else -1 if c[6] == "-" else 0
        ps, pe = promoter_window(start, end, strand)
        windows.append({"ext_gene_id": ext_id, "assembly": ASSEMBLY, "window_type": "promoter",
                        "chromosome": chrom, "start": ps, "end": pe, "strand": strand})
        windows.append({"ext_gene_id": ext_id, "assembly": ASSEMBLY, "window_type": "gene_body",
                        "chromosome": chrom, "start": start - 1, "end": end, "strand": strand})

    with gzip.open(CROSSWALK_JSON, "wt", encoding="utf-8") as f:
        json.dump(crosswalk, f)
    with gzip.open(WINDOWS_JSON, "wt", encoding="utf-8") as f:
        json.dump(windows, f)
    print(f"ITAG4.1 genes: {n_genes}; matched to atlas: {matched}/{len(atlas)}")
    print(f"Wrote {CROSSWALK_JSON} ({len(crosswalk)} rows)")
    print(f"Wrote {WINDOWS_JSON} ({len(windows)} rows: promoter + gene_body)")
    print("motifs.json / motif_hits.json intentionally not produced "
          "(require a FIMO/MEME scan over a genome FASTA).")


if __name__ == "__main__":
    main()
