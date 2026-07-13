"""Human + mouse pathway annotations (#38, pathway half) from mygene.info.

Our human/mouse gene ids ARE HGNC/MGI symbols, so mygene maps them directly to Reactome
and WikiPathways memberships — no ENSG cross-map needed. Feeds the existing
pathway_enrichment machinery (which is already species-general).

Outputs (glob-loaded by build_db; loaded live by load_pathways_animal.py):
  pathways_animal.json            [{pathway_id, name, source}]
  pathway_annotations_animal.json.gz  [{gene_id, pathway_id}]

Usage: python backend/scripts/fetch_pathways_animal.py
"""
import gzip
import json
import sqlite3
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
DB = DATA / "grn.sqlite3"
UA = {"User-Agent": "grn-atlas-build/1.0"}


def querymany(symbols, species):
    """POST batches to mygene; return list of hits with pathway fields."""
    out = []
    for i in range(0, len(symbols), 900):
        chunk = symbols[i:i + 900]
        body = ("q=" + ",".join(chunk) + "&scopes=symbol&species=" + species +
                "&fields=pathway.reactome,pathway.wikipathways").encode()
        req = urllib.request.Request("https://mygene.info/v3/query", data=body, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            out.extend(json.load(r))
    return out


def main():
    conn = sqlite3.connect(DB)
    pathways, annos = {}, set()
    for species, tax in (("human", "human"), ("mouse", "mouse")):
        syms = [r[0] for r in conn.execute("SELECT id FROM genes WHERE species=?", (species,))]
        symset = set(syms)
        hits = querymany(syms, tax)
        for h in hits:
            gid = h.get("query")
            if gid not in symset or "pathway" not in h:
                continue
            pw = h["pathway"]
            for key, source in (("reactome", "Reactome"), ("wikipathways", "WikiPathways")):
                entries = pw.get(key)
                if not entries:
                    continue
                if isinstance(entries, dict):
                    entries = [entries]
                for e in entries:
                    pid, name = e.get("id"), e.get("name")
                    if pid and name:
                        pathways[pid] = {"pathway_id": pid, "name": name, "source": source}
                        annos.add((gid, pid))
        print(f"{species}: {len([a for a in annos])} cumulative annotations")

    (DATA / "pathways_animal.json").write_text(json.dumps(list(pathways.values())))
    with gzip.open(DATA / "pathway_annotations_animal.json.gz", "wt", encoding="utf-8") as f:
        json.dump([{"gene_id": g, "pathway_id": p} for g, p in sorted(annos)], f)
    print(f"pathways: {len(pathways)}  annotations: {len(annos)}  "
          f"genes: {len({g for g, _ in annos})}")


if __name__ == "__main__":
    main()
