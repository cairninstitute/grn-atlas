"""Generic sequence-context fetcher (config-driven) — replaces the per-species
fetch_{petunia,arabidopsis}_seqctx.py. Handles the common PLAZA-identity pattern:
atlas gene ids == reference gene ids, so an identity crosswalk + promoter/gene-body
windows are derived directly from a PLAZA-style GFF.

(Tomato is a special case — an SGN ITAG4.1 version lift-over — and keeps its bespoke
fetch_tomato_seqctx.py.)

Outputs (loaded by load_seqctx.py; also glob-loaded by build_db):
  gene_id_crosswalk_<species>.json.gz , gene_windows_<species>.json.gz

Usage: python backend/scripts/fetch_seqctx.py <species>
"""
import gzip
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import species_config  # noqa: E402

DATA = Path(__file__).parent.parent / "data"
DB = DATA / "grn.sqlite3"
UA = {"User-Agent": "grn-atlas-build/1.0"}


def promoter_window(start, end, strand, up, down):
    if strand >= 0:
        tss0 = start - 1
        return max(0, tss0 - up), tss0 + down
    return max(0, end - down), end + up


def main(species):
    cfg = species_config.get(species)
    if not cfg:
        sys.exit(f"unknown species '{species}' (add it to species_config.py)")
    if cfg["seqctx_style"] != "plaza_identity":
        sys.exit(f"{species} uses seqctx_style={cfg['seqctx_style']!r}; use its bespoke script")
    if not cfg["gff_url"]:
        sys.exit(f"{species} has no gff_url in species_config")

    assembly = cfg["assembly"]
    up, down = cfg["promoter"]
    conn = sqlite3.connect(DB)
    keep = {r[0] for r in conn.execute("SELECT id FROM genes WHERE species=?", (species,))}
    conn.close()
    print(f"Atlas {species} genes: {len(keep)}\nDownloading GFF…")

    req = urllib.request.Request(cfg["gff_url"], headers=UA)
    with urllib.request.urlopen(req, timeout=180) as resp, gzip.GzipFile(fileobj=resp) as gz:
        lines = gz.read().decode("utf-8", "replace").splitlines()

    crosswalk, windows, n = [], [], 0
    for line in lines:
        if not line or line.startswith("#"):
            continue
        c = line.split("\t")
        if len(c) != 9 or c[2] != "gene":
            continue
        attrs = dict(f.split("=", 1) for f in c[8].split(";") if "=" in f)
        gid = attrs.get("gene_id") or attrs.get("ID")
        if gid not in keep:
            continue
        n += 1
        chrom, start, end = c[0], int(c[3]), int(c[4])
        strand = 1 if c[6] == "+" else -1 if c[6] == "-" else 0
        crosswalk.append({"species": species, "atlas_gene_id": gid, "ext_gene_id": gid,
                          "ext_assembly": assembly, "relation": "1:1"})
        ps, pe = promoter_window(start, end, strand, up, down)
        windows.append({"ext_gene_id": gid, "assembly": assembly, "window_type": "promoter",
                        "chromosome": chrom, "start": ps, "end": pe, "strand": strand})
        windows.append({"ext_gene_id": gid, "assembly": assembly, "window_type": "gene_body",
                        "chromosome": chrom, "start": start - 1, "end": end, "strand": strand})

    cw_path = DATA / f"gene_id_crosswalk_{species}.json.gz"
    win_path = DATA / f"gene_windows_{species}.json.gz"
    with gzip.open(cw_path, "wt", encoding="utf-8") as f:
        json.dump(crosswalk, f)
    with gzip.open(win_path, "wt", encoding="utf-8") as f:
        json.dump(windows, f)
    print(f"matched {n} genes\nWrote {cw_path} ({len(crosswalk)})\nWrote {win_path} ({len(windows)})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: fetch_seqctx.py <species>")
    main(sys.argv[1])
