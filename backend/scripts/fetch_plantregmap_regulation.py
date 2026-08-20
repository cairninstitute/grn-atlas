"""
Fetch real TF-target regulatory edges from PlantRegMap for any plant species
configured in species_config.py.  Prefers the higher-confidence FunTFBS network
(functional TF binding sites filtered by DNase-seq); falls back to the broader
motif-based network when FunTFBS is unavailable.

Writes regulation_{species}.tsv in the same format build_db.py already consumes.

Usage:
    python backend/scripts/fetch_plantregmap_regulation.py petunia
    python backend/scripts/fetch_plantregmap_regulation.py tomato
    python backend/scripts/fetch_plantregmap_regulation.py all
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import species_config  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data"
PLAZA_GENES_JSON = DATA_DIR / "genome_genes_plaza.json"
UA = {"User-Agent": "Mozilla/5.0 (grn-atlas-build)"}

FUNTFBS_URL = ("https://plantregmap.gao-lab.org/download_ftp.php?filepath="
               "08-download/{species}/binding/regulation_from_FunTFBS_{suffix}.txt")
MOTIF_URL = ("https://plantregmap.gao-lab.org/download_ftp.php?filepath="
             "08-download/{species}/binding/regulation_from_motif_{suffix}.txt")

FUNTFBS_CONFIDENCE = 0.65
MOTIF_CONFIDENCE = 0.50


def base_id(gene_id):
    return gene_id.split(".")[0]


def _download(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read().decode("utf-8", "replace")
    if "find the file" in data.lower():
        return None
    return data.splitlines()


def load_gene_base_map(species):
    """base gene id -> our atlas gene id (with version), from PLAZA gene set."""
    genes = json.loads(PLAZA_GENES_JSON.read_text())
    return {base_id(gid): gid for gid, g in genes.items() if g.get("species") == species}


def parse_edges(lines, base_map):
    """Parse PlantRegMap regulation lines (both FunTFBS and motif format).

    FunTFBS format: TF \\t target \\t regulation_type \\t confidence \\t source
    Motif format:   TF \\t regulates \\t target \\t motif \\t species \\t - \\t -
    """
    edges = []
    seen = set()
    unmapped = 0
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        tf_raw = parts[0]
        target_raw = parts[2]
        tf = base_map.get(base_id(tf_raw))
        target = base_map.get(base_id(target_raw))
        if not tf or not target or tf == target:
            if not (tf and target):
                unmapped += 1
            continue
        key = (tf, target)
        if key in seen:
            continue
        seen.add(key)
        edges.append((tf, target))
    return edges, unmapped


def fetch_species(species):
    cfg = species_config.get(species)
    if not cfg:
        sys.exit(f"Unknown species '{species}' — add it to species_config.py")
    prm = cfg.get("plantregmap")
    if not prm:
        sys.exit(f"Species '{species}' has no plantregmap config in species_config.py")

    base_map = load_gene_base_map(species)
    print(f"{species}: {len(base_map)} genes in our set")

    funtfbs_url = FUNTFBS_URL.format(species=prm["species"], suffix=prm["suffix"])
    motif_url = MOTIF_URL.format(species=prm["species"], suffix=prm["suffix"])

    print(f"Trying FunTFBS: {funtfbs_url}")
    lines = _download(funtfbs_url)
    if lines is not None:
        source_tag = "FunTFBS"
        confidence = FUNTFBS_CONFIDENCE
        print(f"  FunTFBS available: {len(lines)} raw lines")
    else:
        print("  FunTFBS not available — falling back to motif-based regulation")
        print(f"  Downloading: {motif_url}")
        lines = _download(motif_url)
        if lines is None:
            print(f"  ERROR: neither FunTFBS nor motif file available for {species}")
            return 0
        source_tag = "motif"
        confidence = MOTIF_CONFIDENCE
        print(f"  Motif-based regulation: {len(lines)} raw lines")

    edges, unmapped = parse_edges(lines, base_map)

    out_path = DATA_DIR / f"regulation_{species}.tsv"
    with open(out_path, "w") as f:
        for tf, target in edges:
            f.write(f"{tf}\t{target}\tregulation\t{confidence}\t{source_tag}\n")
    print(f"Wrote {out_path}: {len(edges)} edges ({source_tag}, confidence={confidence})")
    if unmapped:
        print(f"  ({unmapped} raw edges had an endpoint outside our gene set)")
    return len(edges)


TOBACCO_PLANTREGMAP = {
    "species": "Nicotiana_tabacum",
    "suffix": "48385",
}


def fetch_tobacco_raw():
    """Fetch tobacco PlantRegMap edges in raw LOC gene format (no atlas mapping).

    Tobacco is not in the atlas gene set — its edges are projected onto
    petunia/tomato via BLAST RBH orthologs in build_db.py."""
    motif_url = MOTIF_URL.format(**TOBACCO_PLANTREGMAP)
    print(f"tobacco: fetching raw PlantRegMap edges")
    print(f"  Downloading: {motif_url}")
    lines = _download(motif_url)
    if lines is None:
        funtfbs_url = FUNTFBS_URL.format(**TOBACCO_PLANTREGMAP)
        print(f"  Trying FunTFBS: {funtfbs_url}")
        lines = _download(funtfbs_url)
    if lines is None:
        print("  ERROR: could not download tobacco regulation data")
        return
    out_path = DATA_DIR / "regulation_tobacco_raw.tsv"
    with open(out_path, "w") as f:
        for line in lines:
            f.write(line + "\n")
    print(f"  Wrote {out_path}: {len(lines)} lines (raw LOC gene IDs)")


def main():
    if len(sys.argv) < 2:
        print("Usage: fetch_plantregmap_regulation.py <species|all>")
        sys.exit(1)

    target = sys.argv[1]
    if target == "all":
        species_list = [sp for sp, cfg in species_config.SPECIES.items()
                        if cfg.get("plantregmap")]
        species_list.append("tobacco")
    elif target == "tobacco":
        fetch_tobacco_raw()
        return
    else:
        species_list = [target]

    for sp in species_list:
        if sp == "tobacco":
            fetch_tobacco_raw()
        else:
            fetch_species(sp)
        print()


if __name__ == "__main__":
    main()
