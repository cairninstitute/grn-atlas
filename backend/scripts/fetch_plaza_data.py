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

The PLAZA petunia annotation (P. axillaris v1.6.2) is scaffold-level. We lift its
gene coordinates onto 7 chromosomes using the DNA Zoo Hi-C .assembly file (same
v1.6.2 annotation, so gene ids are identical and PLAZA orthology is preserved).
If that file is unavailable, petunia falls back to its largest scaffolds.

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
from bisect import bisect_right
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
SCAFFOLD_CAP = 25                  # fallback: max scaffolds to keep per species
UA = {"User-Agent": "grn-atlas-build/1.0 (genome data enrichment)"}

# DNA Zoo Hi-C assembly of P. axillaris v1.6.2 (7 chromosomes). 3D-DNA .assembly
# format: scaffolds split into fragments, ordered/oriented into super-scaffolds.
PETUNIA_HIC_ASSEMBLY = (
    "https://www.dropbox.com/s/81n270pmo0ssej2/"
    "Petunia_axillaris_v1.6.2_genome_HiC.assembly?dl=1"
)
PETUNIA_N_CHROMS = 7


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


def build_petunia_lift():
    """Parse the DNA Zoo Hi-C .assembly and return (lift, chrom_len):
      lift(scaffold, pos) -> (chrom_name, chrom_pos) or None
      chrom_len          -> {chrom_name: length}
    Returns (None, None) if the assembly cannot be fetched/parsed."""
    print("Downloading petunia Hi-C assembly (for scaffold->chromosome liftover)…")
    try:
        req = urllib.request.Request(PETUNIA_HIC_ASSEMBLY, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  ! could not fetch Hi-C assembly ({e}); falling back to scaffolds")
        return None, None

    frags = {}          # cprops index -> (scaffold, length)
    scaf_frags = {}     # scaffold -> [(index, length), …] in scaffold order
    order_lines = []    # each = signed cprops indices forming a super-scaffold
    for line in raw.splitlines():
        if line.startswith(">"):
            name, idx, length = line[1:].rsplit(" ", 2)
            idx, length = int(idx), int(length)
            scaf = name.split(":::")[0]
            frags[idx] = (scaf, length)
            scaf_frags.setdefault(scaf, []).append((idx, length))
        elif line.strip():
            order_lines.append([int(x) for x in line.split()])

    # The 7 longest super-scaffolds are the chromosomes (ranked largest first).
    ranked = sorted(
        ((sum(frags[abs(x)][1] for x in ol), li) for li, ol in enumerate(order_lines)),
        reverse=True)[:PETUNIA_N_CHROMS]
    chrom_of_line = {li: str(rank + 1) for rank, (_, li) in enumerate(ranked)}
    chrom_len = {str(rank + 1): L for rank, (L, _) in enumerate(ranked)}

    # Placement of each fragment on its chromosome.
    place = {}          # index -> (chrom_name, chrom_offset, sign, length)
    for li, ol in enumerate(order_lines):
        chrom = chrom_of_line.get(li)
        if chrom is None:
            continue
        off = 0
        for x in ol:
            idx, length = abs(x), frags[abs(x)][1]
            place[idx] = (chrom, off, 1 if x > 0 else -1, length)
            off += length

    # Per-scaffold fragment start offsets, for position lookup.
    scaf_lookup = {}
    for scaf, fl in scaf_frags.items():
        starts, items, off = [], [], 0
        for idx, length in fl:
            starts.append(off); items.append((idx, length)); off += length
        scaf_lookup[scaf] = (starts, items)

    def lift(scaf, pos):
        entry = scaf_lookup.get(scaf)
        if not entry:
            return None
        starts, items = entry
        j = bisect_right(starts, pos) - 1
        if j < 0:
            return None
        idx, _ = items[j]
        placed = place.get(idx)
        if not placed:
            return None
        chrom, coff, sign, flen = placed
        off_in = pos - starts[j]
        return chrom, coff + off_in if sign > 0 else coff + (flen - off_in)

    print(f"  lifted assembly: {PETUNIA_N_CHROMS} chromosomes, "
          f"{sum(chrom_len.values()) / 1e9:.2f} Gb anchored")
    return lift, chrom_len


def lift_petunia(located, lift):
    """Remap scaffold-based petunia genes to chromosome coordinates; drop genes
    on unplaced scaffolds."""
    out = {}
    for gid, (chrom, start, end, strand, symbol) in located.items():
        r = lift(chrom, (start + end) // 2)
        if not r:
            continue
        new_chrom, pos = r
        out[gid] = (new_chrom, pos, pos + (end - start), strand, symbol)
    print(f"  petunia: {len(out)}/{len(located)} genes lifted onto chromosomes")
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

    petunia_lift, _ = build_petunia_lift()

    positions = {}
    genes = {}
    for sp, species in PLAZA_SPECIES.items():
        located = parse_gff(sp, wanted[sp])
        if sp == "pax" and petunia_lift:
            located = lift_petunia(located, petunia_lift)
        elif sp in NEW_SPECIES:
            located, _ = cap_scaffolds(located)  # fallback (e.g. Hi-C unavailable)
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
