"""Fetch TF-target edges from DoRothEA (via OmniPath) for human and mouse.

DoRothEA aggregates TF-target evidence from multiple sources (ChIP-seq,
literature, TF binding motifs, gene expression) and assigns confidence
levels A-D (A = highest). We keep A+B edges as a second network source
alongside TRRUST.

Usage:
    python backend/scripts/fetch_dorothea.py          # both species
    python backend/scripts/fetch_dorothea.py human     # one species
    python backend/scripts/fetch_dorothea.py mouse
"""
import sys
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

SPECIES = {
    "human": {"taxid": 9606, "out": "dorothea_human.tsv"},
    "mouse": {"taxid": 10090, "out": "dorothea_mouse.tsv"},
}

URL_TEMPLATE = ("https://omnipathdb.org/interactions?"
                "datasets=dorothea&genesymbols=yes&fields=dorothea_level"
                "&organisms={taxid}&license=academic")


def fetch_species(name, cfg):
    url = URL_TEMPLATE.format(taxid=cfg["taxid"])
    print(f"Fetching DoRothEA {name} TF-target edges from OmniPath...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    data = resp.read().decode("utf-8")
    lines = data.splitlines()
    header = lines[0].split("\t")
    print(f"  Raw lines: {len(lines) - 1}")

    col = {n: i for i, n in enumerate(header)}

    edges = []
    seen = set()
    for line in lines[1:]:
        parts = line.split("\t")
        tf = parts[col["source_genesymbol"]]
        target = parts[col["target_genesymbol"]]
        level = parts[col["dorothea_level"]].split(";")[0]

        if level not in ("A", "B"):
            continue
        if "COMPLEX:" in tf or "COMPLEX:" in target:
            continue

        is_stim = parts[col["is_stimulation"]] == "True"
        is_inhib = parts[col["is_inhibition"]] == "True"
        if is_stim and not is_inhib:
            reg = "activation"
        elif is_inhib and not is_stim:
            reg = "repression"
        else:
            reg = "regulation"

        conf = 0.90 if level == "A" else 0.75
        key = (tf, target)
        if key in seen:
            continue
        seen.add(key)
        edges.append((tf, target, reg, conf, level))

    out_path = DATA_DIR / cfg["out"]
    with open(out_path, "w") as f:
        for tf, target, reg, conf, level in edges:
            f.write(f"{tf}\t{target}\t{reg}\t{conf}\tDoRothEA-{level}\n")

    a_count = sum(1 for e in edges if e[4] == "A")
    b_count = sum(1 for e in edges if e[4] == "B")
    print(f"  Wrote {out_path}: {len(edges)} edges (A={a_count}, B={b_count})")


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(SPECIES.keys())
    for name in targets:
        if name not in SPECIES:
            print(f"Unknown species: {name}. Available: {list(SPECIES.keys())}")
            continue
        fetch_species(name, SPECIES[name])


if __name__ == "__main__":
    main()
