"""Pathway annotations for plant species (#5), from Plant Reactome (Gramene).

Complements GO enrichment with curated *pathway* membership (metabolism, signalling,
etc.). Plant Reactome uses native gene IDs: AGI (AT…) for Arabidopsis — direct match;
Solyc…​.<ver> for tomato — matched version-tolerantly to our atlas IDs.

Human/mouse pathways (Reactome, Ensembl gene IDs) need an ENSG→symbol map and are a
follow-up; this covers the plant side (arabidopsis, tomato).

Outputs (loaded by load_pathways.py; also glob-loaded by build_db on full rebuild):
  - pathways.json                 : [{pathway_id, name, source}]
  - pathway_annotations.json.gz   : [{gene_id, pathway_id}]

Usage: python backend/scripts/fetch_pathways.py
"""
import gzip
import json
import sqlite3
import urllib.request
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
DB = DATA / "grn.sqlite3"
URL = "https://plantreactome.gramene.org/download/current/Ensembl2PlantReactome_All_Levels.txt"
SPECIES = {"Arabidopsis thaliana": "arabidopsis", "Solanum lycopersicum": "tomato"}
UA = {"User-Agent": "grn-atlas-build/1.0"}


def _versionless(gid):
    return gid.rsplit(".", 1)[0]


def main():
    conn = sqlite3.connect(DB)
    # our atlas gene ids per species, plus a versionless index for tomato matching
    atlas = defaultdict(set)
    vindex = {}   # versionless -> full atlas id (tomato)
    for sp in SPECIES.values():
        for (gid,) in conn.execute("SELECT id FROM genes WHERE species=?", (sp,)):
            atlas[sp].add(gid)
            vindex[_versionless(gid)] = gid
    conn.close()

    print("Downloading Plant Reactome…")
    req = urllib.request.Request(URL, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as resp:
        lines = resp.read().decode("utf-8", "replace").splitlines()

    pathways = {}
    annos = set()
    for line in lines:
        c = line.split("\t")
        if len(c) < 6 or c[5] not in SPECIES:
            continue
        sp = SPECIES[c[5]]
        rid, name, gid = c[1], c[3], c[0]
        # match to an atlas gene id (direct, else version-tolerant)
        if gid in atlas[sp]:
            atlas_id = gid
        else:
            atlas_id = vindex.get(_versionless(gid))
            if atlas_id is None:
                continue
        pathways[rid] = {"pathway_id": rid, "name": name, "source": "PlantReactome"}
        annos.add((atlas_id, rid))

    with open(DATA / "pathways.json", "w", encoding="utf-8") as f:
        json.dump(list(pathways.values()), f)
    with gzip.open(DATA / "pathway_annotations.json.gz", "wt", encoding="utf-8") as f:
        json.dump([{"gene_id": g, "pathway_id": p} for g, p in sorted(annos)], f)

    per_sp = defaultdict(int)
    ann_by_gene = {g for g, _ in annos}
    print(f"pathways: {len(pathways)}  annotations: {len(annos)}  genes annotated: {len(ann_by_gene)}")
    for g, _ in annos:
        per_sp["arabidopsis" if g.startswith("AT") else "tomato"] += 1
    print("annotations by species:", dict(per_sp))


if __name__ == "__main__":
    main()
