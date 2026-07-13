"""Generic expression-matrix builder (config-driven) — replaces the per-species
fetch_{petunia,tomato,arabidopsis}_expression.py. Also the home of the shared
ENA-streaming + kallisto helpers.

For a species with a curated `expr_panel` + kallisto `expr_index` in species_config:
streams subsampled reads from ENA, pseudo-aligns with kallisto, aggregates transcript
TPM to per-gene TPM (gene_of), and writes expression_<species>.json.gz.

Shallow/predicted (subsampled) — relative + co-expression signal, not absolute levels.
Per-run kallisto output is cached under data/expr/quant/<run>/ and reused on re-run.

Usage: python backend/scripts/fetch_expression.py <species>
       EXPR_SUBSAMPLE=3000000 (env) controls reads/run.
"""
import gzip
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import species_config  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
EXPR = DATA / "expr"
QUANT = EXPR / "quant"
KALLISTO = HERE.parent.parent / "tools" / "kallisto" / "kallisto"
N_READS = int(os.environ.get("EXPR_SUBSAMPLE", "3000000"))
UA = {"User-Agent": "grn-atlas/1.0"}


def ena_fastq_urls(run):
    url = ("https://www.ebi.ac.uk/ena/portal/api/filereport?accession=" + run +
           "&result=read_run&fields=fastq_ftp&format=tsv")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        lines = r.read().decode().splitlines()
    if len(lines) < 2 or not lines[1].strip():
        return []
    return ["https://" + p for p in lines[1].split("\t")[-1].split(";") if p]


def stream_subsample(url, dest, n_reads):
    cmd = f"curl -s --max-time 1200 '{url}' | zcat 2>/dev/null | head -n {n_reads * 4} > '{dest}'"
    subprocess.run(["bash", "-c", cmd], check=False)
    return dest.exists() and dest.stat().st_size > 0


def quant_run(run, idx):
    """Download (subsampled) + kallisto quant one run. Returns abundance.tsv path."""
    outdir = QUANT / run
    ab = outdir / "abundance.tsv"
    if ab.exists():
        return ab
    outdir.mkdir(parents=True, exist_ok=True)
    urls = ena_fastq_urls(run)
    if not urls:
        print(f"  [{run}] no fastq urls", flush=True)
        return None
    fastqs = []
    paired = len(urls) >= 2 and any(u.endswith("_1.fastq.gz") for u in urls)
    try:
        if paired:
            u1 = next(u for u in urls if u.endswith("_1.fastq.gz"))
            u2 = next(u for u in urls if u.endswith("_2.fastq.gz"))
            f1, f2 = EXPR / f"{run}_1.fq", EXPR / f"{run}_2.fq"
            if not (stream_subsample(u1, f1, N_READS) and stream_subsample(u2, f2, N_READS)):
                print(f"  [{run}] download failed", flush=True)
                return None
            fastqs = [str(f1), str(f2)]
            kcmd = [str(KALLISTO), "quant", "-i", str(idx), "-o", str(outdir), "-t", "2"] + fastqs
        else:
            u = next((u for u in urls if u.endswith(".fastq.gz")), urls[0])
            f = EXPR / f"{run}.fq"
            if not stream_subsample(u, f, N_READS):
                print(f"  [{run}] download failed", flush=True)
                return None
            fastqs = [str(f)]
            kcmd = [str(KALLISTO), "quant", "-i", str(idx), "-o", str(outdir),
                    "-t", "2", "--single", "-l", "200", "-s", "20"] + fastqs
        r = subprocess.run(kcmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  [{run}] kallisto failed: {r.stderr[-300:]}", flush=True)
            return None
        return ab if ab.exists() else None
    finally:
        for f in fastqs:
            try:
                os.remove(f)
            except OSError:
                pass


def gene_of(target_id):
    """reference transcript id -> atlas gene id (strip the trailing isoform component)."""
    return target_id.rsplit(".", 1)[0]


def main(species):
    cfg = species_config.get(species)
    if not cfg:
        sys.exit(f"unknown species '{species}'")
    panel = cfg.get("expr_panel") or {}
    if not panel:
        sys.exit(f"{species} has no expr_panel in species_config")
    idx = EXPR / cfg["expr_index"]
    if not idx.exists():
        sys.exit(f"missing kallisto index {idx} (build it from {cfg['cds_url']})")

    runs = list(panel)
    per_sample = {}
    for i, run in enumerate(runs, 1):
        print(f"[{i}/{len(runs)}] {run} ({panel[run][0]})", flush=True)
        ab = quant_run(run, idx)
        if ab is None:
            continue
        gene_tpm = {}
        with open(ab) as fh:
            next(fh)
            for line in fh:
                p = line.rstrip("\n").split("\t")
                g = gene_of(p[0])
                gene_tpm[g] = gene_tpm.get(g, 0.0) + float(p[4])
        per_sample[run] = gene_tpm

    ok = [r for r in runs if r in per_sample]
    genes = sorted({g for tpm in per_sample.values() for g in tpm})
    matrix = {g: [round(per_sample[r].get(g, 0.0), 3) for r in ok] for g in genes}
    out = {
        "meta": {"assembly": cfg["assembly"],
                 "reference": f"PLAZA Dicots 4.5 {cfg['plaza_code']} CDS (selected transcript)"
                              if cfg.get("plaza_code") else "reference CDS",
                 "quantifier": "kallisto 0.50.1", "source": "ENA/SRA public RNA-seq, subsampled",
                 "n_reads_subsample": N_READS, "unit": "TPM",
                 "label": "predicted (shallow subsampled quantification)",
                 "note": "Proof-of-concept expression; relative/co-expression signal, not absolute."},
        "samples": [{"run": r, "tissue": panel[r][0], "study": panel[r][1]} for r in ok],
        "genes": matrix,
    }
    out_path = DATA / f"expression_{species}.json.gz"
    with gzip.open(out_path, "wt") as fh:
        json.dump(out, fh)
    print(f"\nwrote {out_path}  ({len(ok)} samples, {len(genes)} genes)", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: fetch_expression.py <species>")
    main(sys.argv[1])
