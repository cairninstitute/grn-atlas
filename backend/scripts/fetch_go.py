"""
One-time enrichment: fetch Gene Ontology annotations for all species so the app
can run GO-term enrichment offline. Plant GO comes from PLAZA (already propagated
up the GO hierarchy, which is what enrichment needs); human/mouse GO from
mygene.info (same source used for gene names).

Output (committed): go_annotations.json
  { "terms": { GO_ID: [name, namespace] },
    "annotations": { gene_id: [GO_ID, ...] } }

Usage: python backend/scripts/fetch_go.py
"""
import gzip
import json
import sqlite3
import urllib.request
import urllib.parse
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
OUTPUT_JSON = DATA_DIR / "go_annotations.json.gz"

PLAZA_GO = "https://ftp.psb.ugent.be/pub/plaza/plaza_public_dicots_04_5/GO/go.{sp}.csv.gz"
PLAZA_CODE = {"arabidopsis": "ath", "tomato": "sly", "petunia": "pax"}
UA = {"User-Agent": "grn-atlas-build/1.0 (GO enrichment)"}
MYGENE_BATCH = 800


def load_gene_ids():
    conn = sqlite3.connect(DB_PATH)
    ids = defaultdict(set)
    for gid, sp in conn.execute("SELECT id, species FROM genes"):
        ids[sp].add(gid)
    conn.close()
    return ids


def stream_lines(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        with gzip.GzipFile(fileobj=resp) as gz:
            for raw in gz:
                yield raw.decode("utf-8", "replace").rstrip("\n")


def fetch_plaza_go(species, want_ids, terms, annotations):
    code = PLAZA_CODE[species]
    print(f"Downloading PLAZA GO for {species} ({code})…")
    base_map = {g.split(".")[0]: g for g in want_ids}  # tolerate version differences
    n = 0
    for line in stream_lines(PLAZA_GO.format(sp=code)):
        if not line or line.startswith("#"):
            continue
        c = line.split("\t")
        if len(c) < 8:
            continue
        gid = want_ids.__contains__(c[0]) and c[0] or base_map.get(c[0].split(".")[0])
        if not gid:
            continue
        go_id, name = c[2], c[7]
        terms.setdefault(go_id, [name, ""])
        annotations[gid].add(go_id)
        n += 1
    print(f"  {species}: {n} annotations")


def fetch_mygene_go(species, want_ids, terms, annotations):
    print(f"Fetching {species} GO from mygene.info ({len(want_ids)} genes)…")
    symbols = sorted(want_ids)
    for i in range(0, len(symbols), MYGENE_BATCH):
        chunk = symbols[i:i + MYGENE_BATCH]
        body = urllib.parse.urlencode({
            "q": ",".join(chunk), "scopes": "symbol",
            "species": species, "fields": "go",
        }).encode()
        req = urllib.request.Request("https://mygene.info/v3/query", data=body,
                                     headers={**UA, "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            hits = json.loads(resp.read())
        for hit in hits:
            gid = hit.get("query")
            go = hit.get("go")
            if not gid or gid not in want_ids or not go:
                continue
            for cat, entries in go.items():  # BP / CC / MF
                if isinstance(entries, dict):
                    entries = [entries]
                for e in entries or []:
                    go_id, name = e.get("id"), e.get("term")
                    if not go_id:
                        continue
                    terms.setdefault(go_id, [name or go_id, cat])
                    annotations[gid].add(go_id)
        print(f"  batch {i // MYGENE_BATCH + 1}: {len(annotations)} genes annotated so far")


def main():
    gene_ids = load_gene_ids()
    terms = {}
    annotations = defaultdict(set)

    for species in ("arabidopsis", "tomato", "petunia"):
        if gene_ids.get(species):
            fetch_plaza_go(species, gene_ids[species], terms, annotations)
    for species in ("human", "mouse"):
        if gene_ids.get(species):
            fetch_mygene_go(species, gene_ids[species], terms, annotations)

    out = {
        "terms": terms,
        "annotations": {g: sorted(t) for g, t in annotations.items()},
    }
    with gzip.open(OUTPUT_JSON, "wt", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"Wrote {OUTPUT_JSON}: {len(terms)} GO terms, {len(annotations)} genes annotated")


if __name__ == "__main__":
    main()
