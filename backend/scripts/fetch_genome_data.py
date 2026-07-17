"""
One-time enrichment step: fetch genomic coordinates and cross-species orthologs
from the OMA browser REST API (https://omabrowser.org/api), and cache the result
to committed JSON so the app never needs network access to serve genome data.

OMA is used because it provides genomic coordinates AND pairwise orthologs from a
single interface, and spans all domains of life (so human<->Arabidopsis, a
cross-kingdom comparison, is covered -- unlike Ensembl Compara).

Outputs (under backend/data/):
  - genome_positions.json : { gene_id: {species, chromosome, start, end, strand} }
  - orthologs.json        : [ {gene_a, species_a, gene_b, species_b, rel_type, score} ]

The script is resumable: progress is checkpointed to .oma_cache.json, so it is
safe to interrupt and re-run (already-resolved genes are skipped).

Usage: python backend/scripts/fetch_genome_data.py
"""
import json
import re
import sqlite3
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

WORKERS = 10  # concurrent OMA requests

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"
POSITIONS_JSON = DATA_DIR / "genome_positions.json"
ORTHOLOGS_JSON = DATA_DIR / "orthologs.json"
CACHE_JSON = DATA_DIR / ".oma_cache.json"

API = "https://omabrowser.org/api"

# Map our internal species names -> OMA genome codes. Extend as species are added.
OMA_CODE = {
    "human": "HUMAN",
    "arabidopsis": "ARATH",
}

AGI_RE = re.compile(r"^AT[1-5CM]G\d{5}$", re.IGNORECASE)


def http_get(url, retries=4):
    """GET JSON with basic backoff on rate-limit / transient errors."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "grn-atlas-build/1.0 (https://github.com/; genome data enrichment)",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    return None


class Cache:
    """Resumable on-disk checkpoint."""

    def __init__(self, path):
        self.path = path
        if path.exists():
            self.data = json.loads(path.read_text())
        else:
            self.data = {"positions": {}, "orthologs": {}, "omaid_to_agi": {}, "done_human": []}
        self.data.setdefault("positions", {})
        self.data.setdefault("orthologs", {})
        self.data.setdefault("omaid_to_agi", {})
        self.data.setdefault("done_human", [])

    def save(self):
        self.path.write_text(json.dumps(self.data))


def load_db_genes():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    human = [r["id"] for r in conn.execute("SELECT id FROM genes WHERE species='human'")]
    arab = {r["id"].upper() for r in conn.execute("SELECT id FROM genes WHERE species='arabidopsis'")}
    conn.close()
    return human, arab


def loc_of(entry):
    """Extract {chromosome,start,end,strand} from an OMA protein/ortholog entry."""
    locus = entry.get("locus") or {}
    chrom = entry.get("chromosome")
    if chrom is None or locus.get("start") is None:
        return None
    return {
        "chromosome": str(chrom),
        "start": int(locus["start"]),
        "end": int(locus.get("end", locus["start"])),
        "strand": int(locus.get("strand", 0) or 0),
    }


_agi_lock = threading.Lock()


def resolve_agi(omaid, cache):
    """Map an OMA Arabidopsis entry to its AGI locus id (e.g. AT1G01060)."""
    with _agi_lock:
        if omaid in cache.data["omaid_to_agi"]:
            return cache.data["omaid_to_agi"][omaid]
    agi = None
    xrefs = http_get(f"{API}/protein/{omaid}/xref/")
    if xrefs:
        for x in xrefs:
            val = str(x.get("xref", ""))
            if AGI_RE.match(val):
                agi = val.upper()
                break
    with _agi_lock:
        cache.data["omaid_to_agi"][omaid] = agi
    return agi


def find_human_entry(symbol):
    """Resolve a human gene symbol to its OMA HUMAN entry number via xref search."""
    hits = http_get(f"{API}/xref/?search={urllib.parse.quote(symbol)}")
    if not hits:
        return None
    exact = [h for h in hits if h.get("genome", {}).get("code") == "HUMAN"
             and str(h.get("xref", "")).upper() == symbol.upper()]
    pool = exact or [h for h in hits if h.get("genome", {}).get("code") == "HUMAN"]
    return pool[0]["entry_nr"] if pool else None


def process_symbol(symbol, arab_ids, cache):
    """Fetch coords + Arabidopsis orthologs for one human gene. Returns a dict
    of results to be merged into the cache by the main thread."""
    ARATH = OMA_CODE["arabidopsis"]
    out = {"positions": {}, "orthologs": {}}
    entry_nr = find_human_entry(symbol)
    if not entry_nr:
        return out
    prot = http_get(f"{API}/protein/{entry_nr}/")
    loc = loc_of(prot) if prot else None
    if loc:
        out["positions"][symbol] = {"species": "human", **loc}
    for o in http_get(f"{API}/protein/{entry_nr}/orthologs/") or []:
        if o.get("species", {}).get("code") != ARATH:
            continue
        agi = resolve_agi(o["omaid"], cache)
        if not agi or agi.upper() not in arab_ids:
            continue
        aloc = loc_of(o)
        if aloc:
            out["positions"][agi] = {"species": "arabidopsis", **aloc}
        out["orthologs"][f"{symbol}|{agi}"] = {
            "gene_a": symbol, "species_a": "human",
            "gene_b": agi, "species_b": "arabidopsis",
            "rel_type": o.get("rel_type", ""),
            "score": o.get("score"),
        }
    return out


def main():
    human_genes, arab_ids = load_db_genes()
    cache = Cache(CACHE_JSON)
    done = set(cache.data["done_human"])
    pending = [s for s in human_genes if s not in done]

    print(f"Human genes: {len(human_genes)} ({len(done)} done, {len(pending)} pending)")
    print(f"Arabidopsis genes in DB: {len(arab_ids)}")

    processed = len(done)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(process_symbol, s, arab_ids, cache): s for s in pending}
        for fut in as_completed(futures):
            symbol = futures[fut]
            try:
                out = fut.result()
                cache.data["positions"].update(out["positions"])
                cache.data["orthologs"].update(out["orthologs"])
            except Exception as e:  # keep going; resumable
                print(f"  ! {symbol}: {e}")
            done.add(symbol)
            processed += 1
            if processed % 50 == 0:
                cache.data["done_human"] = sorted(done)
                cache.save()
                print(f"  {processed}/{len(human_genes)} processed, "
                      f"{len(cache.data['positions'])} positions, "
                      f"{len(cache.data['orthologs'])} ortholog pairs")

    cache.data["done_human"] = sorted(done)
    cache.save()

    # Emit final committed caches.
    POSITIONS_JSON.write_text(json.dumps(cache.data["positions"], indent=1, sort_keys=True))
    ORTHOLOGS_JSON.write_text(json.dumps(
        sorted(cache.data["orthologs"].values(), key=lambda o: (o["gene_a"], o["gene_b"])),
        indent=1))
    print(f"Wrote {POSITIONS_JSON} ({len(cache.data['positions'])} positions)")
    print(f"Wrote {ORTHOLOGS_JSON} ({len(cache.data['orthologs'])} ortholog pairs)")


if __name__ == "__main__":
    main()
