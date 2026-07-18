"""
One-time enrichment step for the PLANT side of the genome comparison: fetch gene
coordinates and cross-species orthologs for Arabidopsis, tomato, and petunia from
PLAZA Dicots 4.5 (https://bioinformatics.psb.ugent.be/plaza/), and cache to
committed JSON so runtime needs no network access.

PLAZA is used for plants because petunia is absent from OMA. PLAZA Dicots
provides all three species with a single integrative-orthology table and
per-species GFF annotations, and its Arabidopsis gene ids are AGI locus codes
(e.g. AT1G01020), which match our existing Arabidopsis genes -- so Arabidopsis is
the shared join point between the OMA (animal) and PLAZA (plant) data.

Note: the PLAZA petunia assembly (P. axillaris v1.6.2) is scaffold-level, not
chromosome-level, so petunia is capped to its largest scaffolds (by gene count)
to keep the ideogram legible.

Outputs (under backend/data/):
  - plaza_positions.json     : { gene_id: {species, chromosome, start, end, strand} }
  - orthologs_plaza.json     : [ {gene_a, species_a, gene_b, species_b, rel_type, score} ]
  - genome_genes_plaza.json  : { gene_id: {species, symbol, name, is_tf} }  (tomato/petunia)

Usage: python backend/scripts/fetch_plaza_data.py
"""
import gzip
import json
import sqlite3
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
POSITIONS_JSON = DATA_DIR / "plaza_positions.json"
ORTHOLOGS_JSON = DATA_DIR / "orthologs_plaza.json"
GENES_JSON = DATA_DIR / "genome_genes_plaza.json"

BASE = "https://ftp.psb.ugent.be/pub/plaza/plaza_public_dicots_04_5"
# Anchor points = synteny-based colinear gene pairs. Chosen over the gene-family
# ORTHO relation because synteny is the right (and far sparser, near-1:1) signal
# for a chromosome-vs-chromosome comparison.
ANCHOR_URL = f"{BASE}/IntegrativeOrthology/integrative_orthology.anchor_point.csv.gz"
GFF_URL = "{base}/GFF/{sp}/annotation.selected_transcript.all_features.{sp}.gff3.gz"

# PLAZA 3-letter code -> our internal species name. 'ath' already exists in the
# DB (Arabidopsis); 'sly'/'pax' are new species inserted by build_db.
PLAZA_SPECIES = {
    "ath": "arabidopsis",
    "sly": "tomato",
    "pax": "petunia",
}
NEW_SPECIES = {"sly", "pax"}       # not already in our genes table
SCAFFOLD_CAP = 25                  # max chromosomes/scaffolds to keep per species
UA = {"User-Agent": "grn-atlas-build/1.0 (genome data enrichment)"}


def stream_lines(url):
    """Yield decoded text lines from a gzipped remote file."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        with gzip.GzipFile(fileobj=resp) as gz:
            for raw in gz:
                yield raw.decode("utf-8", "replace").rstrip("\n")


def load_arab_ids():
    conn = sqlite3.connect(DB_PATH)
    ids = {r[0].upper() for r in conn.execute("SELECT id FROM genes WHERE species='arabidopsis'")}
    conn.close()
    return ids


def load_orthologs(arab_ids):
    """Collect unordered ortholog pairs among the PLAZA species. Pairs involving
    Arabidopsis are kept only if the AGI gene exists in our DB. Returns the pair
    list and the set of referenced gene ids per species."""
    seen = set()
    pairs = []
    referenced = set()
    print("Downloading synteny anchor-point table…")
    for line in stream_lines(ANCHOR_URL):
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        qg, qs, og, os_ = parts[0], parts[1], parts[2], parts[3]
        if qs not in PLAZA_SPECIES or os_ not in PLAZA_SPECIES or qs == os_:
            continue
        # Require Arabidopsis genes to be in our DB.
        if qs == "ath" and qg.upper() not in arab_ids:
            continue
        if os_ == "ath" and og.upper() not in arab_ids:
            continue
        key = tuple(sorted([f"{qs}:{qg}", f"{os_}:{og}"]))
        if key in seen:
            continue
        seen.add(key)
        pairs.append({
            "gene_a": qg, "species_a": PLAZA_SPECIES[qs],
            "gene_b": og, "species_b": PLAZA_SPECIES[os_],
            "rel_type": "synteny", "score": None,
        })
        referenced.add((qs, qg))
        referenced.add((os_, og))
    print(f"  kept {len(pairs)} cross-species ortholog pairs")
    return pairs, referenced


def parse_gff(sp, wanted_ids):
    """Parse a species GFF, returning {gene_id: (chromosome,start,end,strand,symbol)}
    for gene features whose id is in wanted_ids (or all, if wanted_ids is None)."""
    out = {}
    print(f"Downloading {sp} GFF…")
    for line in stream_lines(GFF_URL.format(base=BASE, sp=sp)):
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")  # source column contains spaces -> must split on tab
        if len(cols) != 9 or cols[2] != "gene":
            continue
        attrs = {}
        for field in cols[8].split(";"):
            if "=" in field:
                k, v = field.split("=", 1)
                attrs[k] = v
        gid = attrs.get("gene_id") or attrs.get("ID")
        if not gid:
            continue
        if wanted_ids is not None and gid not in wanted_ids:
            continue
        strand = 1 if cols[6] == "+" else -1 if cols[6] == "-" else 0
        out[gid] = (cols[0], int(cols[3]), int(cols[4]), strand, attrs.get("symbol") or gid)
    print(f"  {sp}: {len(out)} genes located")
    return out


def cap_scaffolds(genes):
    """Keep only the SCAFFOLD_CAP most gene-dense chromosomes/scaffolds."""
    counts = {}
    for chrom, *_ in genes.values():
        counts[chrom] = counts.get(chrom, 0) + 1
    if len(counts) <= SCAFFOLD_CAP:
        return genes, set(counts)
    keep = {c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:SCAFFOLD_CAP]}
    kept = {g: v for g, v in genes.items() if v[0] in keep}
    print(f"  capped {len(counts)} scaffolds -> {len(keep)}; {len(kept)} genes retained")
    return kept, keep


def main():
    arab_ids = load_arab_ids()
    print(f"Arabidopsis genes in DB: {len(arab_ids)}")

    pairs, referenced = load_orthologs(arab_ids)

    # Which gene ids we need coordinates for, per PLAZA species code.
    wanted = {sp: set() for sp in PLAZA_SPECIES}
    for sp, gid in referenced:
        wanted[sp].add(gid)

    positions = {}
    genes = {}
    for sp, species in PLAZA_SPECIES.items():
        located = parse_gff(sp, wanted[sp])
        if sp in NEW_SPECIES:
            located, _ = cap_scaffolds(located)
        for gid, (chrom, start, end, strand, symbol) in located.items():
            positions[gid] = {"species": species, "chromosome": chrom,
                              "start": start, "end": end, "strand": strand}
            if sp in NEW_SPECIES:
                genes[gid] = {"species": species, "symbol": symbol,
                             "name": symbol, "is_tf": False}

    # Drop ortholog pairs whose genes were not located (e.g. capped-out petunia).
    located_ids = set(positions)
    pairs = [p for p in pairs if p["gene_a"] in located_ids and p["gene_b"] in located_ids]

    POSITIONS_JSON.write_text(json.dumps(positions, indent=1, sort_keys=True))
    ORTHOLOGS_JSON.write_text(json.dumps(
        sorted(pairs, key=lambda p: (p["gene_a"], p["gene_b"])), indent=1))
    GENES_JSON.write_text(json.dumps(genes, indent=1, sort_keys=True))
    print(f"Wrote {POSITIONS_JSON} ({len(positions)} positions)")
    print(f"Wrote {ORTHOLOGS_JSON} ({len(pairs)} ortholog pairs)")
    print(f"Wrote {GENES_JSON} ({len(genes)} tomato/petunia genes)")


if __name__ == "__main__":
    main()
