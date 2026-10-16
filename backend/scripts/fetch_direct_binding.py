#!/usr/bin/env python3
"""Fetch direct TF-binding data (ChIP-seq / DAP-seq) for atlas species.

Downloads pre-processed TF-target gene tables from public databases:
  - GTRD (human, mouse): meta-cluster TF-target gene tables
  - GEO individual studies (tomato, rice): supplementary peak files

Output: backend/data/direct_binding/<source>_<species>.tsv
Each TSV has columns: tf_symbol\ttarget_id\tsource\taccession\tconfidence

Usage:
    python backend/scripts/fetch_direct_binding.py [--species human,mouse,tomato,rice]
    python backend/scripts/fetch_direct_binding.py --force        # re-download all
    python backend/scripts/fetch_direct_binding.py --list         # show available sources
"""
import argparse
import gzip
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
DATA_DIR = BACKEND_DIR / "data" / "direct_binding"
MANIFEST_PATH = BACKEND_DIR / "source_manifests" / "direct_binding_sources.json"

USER_AGENT = "grn-atlas/1.0"
TIMEOUT = 120


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request(url, timeout=TIMEOUT):
    """Make an HTTP request with our User-Agent header."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)


def _download(url, dest, force=False):
    """Download *url* to *dest*. Skip if file exists and *force* is False.

    Returns True on success, False on failure (with a printed warning).
    """
    if dest.exists() and not force:
        print(f"  Skipping (already exists): {dest.name}")
        return True
    print(f"  Downloading {url} ...")
    try:
        resp = _request(url)
        data = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        print(f"  WARNING: download failed: {exc}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"  Saved {dest.name} ({len(data):,} bytes)")
    return True


def _try_download(primary_url, fallback_urls, dest, force=False):
    """Try primary URL, then each fallback in order. Returns True on first success."""
    if dest.exists() and not force:
        print(f"  Skipping (already exists): {dest.name}")
        return True
    urls = [primary_url] + (fallback_urls or [])
    for url in urls:
        if _download(url, dest, force=True):
            return True
    return False


class _LinkParser(HTMLParser):
    """Extract href values from an HTML page (used for GEO suppl listings)."""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def _list_geo_suppl_links(index_url):
    """Fetch the GEO supplementary directory listing and return file URLs."""
    try:
        resp = _request(index_url)
        html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        print(f"  WARNING: could not list {index_url}: {exc}")
        return []
    parser = _LinkParser()
    parser.feed(html)
    base = index_url.rstrip("/") + "/"
    urls = []
    for href in parser.links:
        if href.startswith("http"):
            urls.append(href)
        elif not href.startswith("/") and not href.startswith("?"):
            urls.append(base + href)
    return urls


PEAK_SUFFIXES = (
    ".narrowpeak.gz", ".broadpeak.gz", ".bed.gz",
    ".narrowpeak", ".broadpeak", ".bed",
    "_peaks.txt.gz", "_peaks.tsv.gz", "_peaks.xls.gz",
    "_targets.txt.gz", "_targets.tsv.gz",
)


def _is_peak_file(filename):
    """Return True if filename looks like a processed peak or target file."""
    lower = filename.lower()
    return any(lower.endswith(s) for s in PEAK_SUFFIXES)


# ---------------------------------------------------------------------------
# Source-specific parsers
# ---------------------------------------------------------------------------

def parse_gtrd_tsv_gz(filepath, source_entry):
    """Parse a GTRD TF-target TSV (gzipped).

    Expected columns specified in manifest; defaults to col 0 = TF, col 1 = target.
    Returns list of (tf_symbol, target_id, source, accession, confidence) tuples.
    """
    cols = source_entry.get("columns", {})
    tf_col = cols.get("tf", 0)
    target_col = cols.get("target", 1)
    version = source_entry.get("version", "")
    species = source_entry["species"]
    accession = f"GTRD-{version}"

    edges = []
    seen = set()
    try:
        with gzip.open(filepath, "rt", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                # Skip header lines
                if lineno == 0 and not line[0].isalnum():
                    continue
                parts = line.split("\t")
                if len(parts) <= max(tf_col, target_col):
                    continue
                tf = parts[tf_col].strip()
                target = parts[target_col].strip()
                if not tf or not target:
                    continue
                # Skip header row if text looks like a column label
                if tf.lower() in ("tf", "transcription_factor", "source", "regulator"):
                    continue
                key = (tf, target)
                if key in seen:
                    continue
                seen.add(key)
                edges.append((tf, target, f"GTRD-{species}", accession, "0.70"))
    except Exception as exc:
        print(f"  WARNING: failed to parse {filepath}: {exc}")
    return edges


def parse_geo_peak_files(suppl_dir, source_entry):
    """Parse peak/target files downloaded from a GEO supplementary directory.

    Handles narrowPeak, broadPeak, BED, and simple target-gene list formats.
    Returns list of (tf_symbol, target_id, source, accession, confidence) tuples.
    """
    if not suppl_dir.is_dir():
        return []

    name = source_entry["name"]
    species = source_entry["species"]
    edges = []
    seen = set()

    for fpath in sorted(suppl_dir.iterdir()):
        if fpath.is_dir():
            continue
        fname = fpath.name.lower()

        # Try to extract TF name from filename (common pattern: TFname_peaks.narrowPeak)
        tf_match = re.match(r"^([A-Za-z][A-Za-z0-9_-]+?)[\._](?:peaks|targets|binding)", fpath.name, re.IGNORECASE)
        tf_symbol = tf_match.group(1) if tf_match else fpath.stem.split("_")[0]

        try:
            opener = gzip.open if fname.endswith(".gz") else open
            with opener(fpath, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("track"):
                        continue
                    parts = line.split("\t")

                    # narrowPeak/broadPeak: >= 6 columns, col 3 = name (sometimes gene)
                    if len(parts) >= 6 and parts[0].startswith(("chr", "Chr", "scaffold")):
                        target = parts[3] if parts[3] != "." else None
                        if target:
                            key = (tf_symbol, target)
                            if key not in seen:
                                seen.add(key)
                                edges.append((tf_symbol, target, f"{name}-{species}", name, "0.60"))
                    # Simple two-column target list: TF\ttarget
                    elif len(parts) >= 2 and not parts[0].startswith(("chr", "Chr")):
                        tf = parts[0].strip()
                        target = parts[1].strip()
                        if tf and target:
                            key = (tf, target)
                            if key not in seen:
                                seen.add(key)
                                edges.append((tf, target, f"{name}-{species}", name, "0.65"))
        except Exception as exc:
            print(f"  WARNING: could not parse {fpath.name}: {exc}")
            continue

    return edges


# ---------------------------------------------------------------------------
# Per-source fetch logic
# ---------------------------------------------------------------------------

def fetch_gtrd(source_entry, force=False):
    """Fetch and parse a GTRD TF-target gene table."""
    species = source_entry["species"]
    filename = source_entry["filename"]
    dest = DATA_DIR / filename
    out_tsv = DATA_DIR / f"gtrd_{species}.tsv"

    ok = _try_download(
        source_entry["url"],
        source_entry.get("fallback_urls", []),
        dest,
        force=force,
    )
    if not ok:
        _print_manual_instructions(source_entry)
        return 0

    print(f"  Parsing {filename} ...")
    edges = parse_gtrd_tsv_gz(dest, source_entry)
    if not edges:
        print(f"  WARNING: no edges parsed from {filename}")
        _print_manual_instructions(source_entry)
        return 0

    _write_edges(out_tsv, edges)
    print(f"  Wrote {out_tsv.name}: {len(edges):,} TF-target edges")
    return len(edges)


def fetch_geo_suppl(source_entry, force=False):
    """Fetch supplementary files from a GEO accession and parse peak/target files."""
    species = source_entry["species"]
    name = source_entry["name"]
    suppl_dir = DATA_DIR / source_entry["filename"]
    out_tsv = DATA_DIR / f"{name.lower()}_{species}.tsv"

    if source_entry.get("requires_peak_calling") and not force:
        # Check if we already have processed output
        if out_tsv.exists() and not force:
            print(f"  Skipping (output exists): {out_tsv.name}")
            return _count_lines(out_tsv)

    # List supplementary files from the GEO FTP directory
    print(f"  Listing supplementary files for {name} ...")
    file_urls = _list_geo_suppl_links(source_entry["url"])

    if not file_urls:
        print(f"  WARNING: no supplementary files found at {source_entry['url']}")
        print(f"  Note: {source_entry.get('note', 'Check GEO accession manually.')}")
        return 0

    # Filter for peak/target files only
    peak_urls = [u for u in file_urls if _is_peak_file(u.split("/")[-1])]

    if not peak_urls:
        print(f"  No processed peak/target files found in {len(file_urls)} supplementary files.")
        print(f"  Available files:")
        for u in file_urls[:10]:
            print(f"    {u.split('/')[-1]}")
        if len(file_urls) > 10:
            print(f"    ... and {len(file_urls) - 10} more")
        note = source_entry.get("note", "")
        if note:
            print(f"  Note: {note}")
        return 0

    # Download peak files
    suppl_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for url in peak_urls:
        fname = url.split("/")[-1]
        dest = suppl_dir / fname
        if _download(url, dest, force=force):
            downloaded += 1

    if downloaded == 0:
        print(f"  WARNING: failed to download any peak files for {name}")
        return 0

    print(f"  Downloaded {downloaded} peak/target files. Parsing ...")
    edges = parse_geo_peak_files(suppl_dir, source_entry)

    if not edges:
        print(f"  No TF-target edges could be extracted (files may need peak calling).")
        return 0

    _write_edges(out_tsv, edges)
    print(f"  Wrote {out_tsv.name}: {len(edges):,} TF-target edges")
    return len(edges)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_edges(path, edges):
    """Write edges to a TSV file with standard columns."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        fh.write("tf_symbol\ttarget_id\tsource\taccession\tconfidence\n")
        for tf, target, source, accession, confidence in edges:
            fh.write(f"{tf}\t{target}\t{source}\t{accession}\t{confidence}\n")


def _count_lines(path):
    """Count data lines (excluding header) in a TSV."""
    if not path.exists():
        return 0
    with open(path) as fh:
        return max(0, sum(1 for _ in fh) - 1)


def _print_manual_instructions(source_entry):
    """Print instructions for manual download when automated fetch fails."""
    species = source_entry["species"]
    filename = source_entry["filename"]
    dest = DATA_DIR / filename
    print()
    print(f"  === MANUAL DOWNLOAD REQUIRED ===")
    print(f"  Source: {source_entry['name']} ({species})")
    print(f"  Description: {source_entry.get('description', '')}")
    print(f"  Try downloading from:")
    print(f"    Primary: {source_entry['url']}")
    for fb in source_entry.get("fallback_urls", []):
        print(f"    Fallback: {fb}")
    print(f"  Save the file to: {dest}")
    print(f"  Then re-run this script.")
    print()


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def fetch_cistrome(source_entry, force=False):
    """Fetch TF-target gene lists from Cistrome DB via their REST API."""
    species = source_entry["species"]
    species_name = {"human": "Homo sapiens", "mouse": "Mus musculus"}.get(species)
    if not species_name:
        print(f"  WARNING: Cistrome DB only covers human/mouse, not {species}")
        return 0

    cache_path = DATA_DIR / source_entry["filename"]
    out_tsv = DATA_DIR / f"cistrome_{species}.tsv"

    if out_tsv.exists() and not force:
        print(f"  Skipping (output exists): {out_tsv.name}")
        return _count_lines(out_tsv)

    max_samples = source_entry.get("max_samples", 200)
    max_targets = source_entry.get("max_targets_per_sample", 500)

    search_url = (
        f"http://cistrome.org/db/api/main_filter_ng?"
        f"cellinfos=all&factors=all&species={species_name.replace(' ', '+')}&peakqc=1"
    )
    print(f"  Querying Cistrome DB sample index for {species_name}...")
    try:
        resp = _request(search_url, timeout=60)
        samples = json.loads(resp.read().decode())
    except Exception as exc:
        print(f"  WARNING: Cistrome API unavailable: {exc}")
        print(f"  Manual: visit http://cistrome.org/db/ and batch-download {species} targets")
        print(f"  Place TSV at: {out_tsv}")
        return 0

    if not isinstance(samples, list) or not samples:
        print(f"  WARNING: Cistrome returned no samples for {species}")
        return 0

    sample_ids = []
    for s in samples[:max_samples * 2]:
        sid = s.get("id") or s.get("DCid")
        if sid:
            sample_ids.append((sid, s.get("factor", "")))
    sample_ids = sample_ids[:max_samples]
    print(f"  Found {len(samples)} samples, fetching targets for {len(sample_ids)}...")

    edges = []
    seen = set()
    stats = {"queried": 0, "errors": 0, "tfs": set()}
    for sid, factor_hint in sample_ids:
        stats["queried"] += 1
        detail_url = f"http://cistrome.org/db/api/inspector?id={sid}"
        try:
            resp = _request(detail_url, timeout=30)
            detail = json.loads(resp.read().decode())
        except Exception:
            stats["errors"] += 1
            continue
        targets = detail.get("targets", [])
        tf = detail.get("factor", factor_hint or "").strip()
        if not tf or not targets:
            continue
        stats["tfs"].add(tf)
        for t in targets[:max_targets]:
            gene = (t.get("gene") or "").strip()
            if not gene or gene == tf:
                continue
            key = (tf, gene)
            if key in seen:
                continue
            seen.add(key)
            score = float(t.get("score", 0)) if t.get("score") else 50.0
            conf = min(0.80, 0.40 + 0.40 * min(score / 100, 1.0))
            edges.append((tf, gene, f"Cistrome-{species}", str(sid), f"{conf:.3f}"))

    if not edges:
        print(f"  WARNING: no edges extracted from Cistrome")
        return 0

    _write_edges(out_tsv, edges)
    print(f"  Wrote {out_tsv.name}: {len(edges):,} edges from {len(stats['tfs'])} TFs "
          f"({stats['errors']} API errors)")

    cache_data = {"species": species, "samples_queried": stats["queried"],
                  "tfs": sorted(stats["tfs"]), "edges": len(edges)}
    cache_path.write_text(json.dumps(cache_data, indent=2))
    return len(edges)


def fetch_manual(source_entry, force=False):
    """Handle sources that require manual preparation."""
    species = source_entry["species"]
    name = source_entry["name"]
    out_tsv = DATA_DIR / f"{name.lower()}_{species}.tsv"
    if out_tsv.exists():
        n = _count_lines(out_tsv)
        print(f"  Found manually prepared {out_tsv.name}: {n:,} edges")
        return n
    print(f"  {source_entry.get('description', name)}")
    print(f"  → Requires manual preparation.")
    note = source_entry.get("note", "")
    if note:
        print(f"  Note: {note}")
    print(f"  Place processed TSV at: {out_tsv}")
    return 0


FORMAT_HANDLERS = {
    "tsv_gz": fetch_gtrd,
    "geo_suppl_dir": fetch_geo_suppl,
    "cistrome_api": fetch_cistrome,
    "manual": fetch_manual,
}


def load_manifest():
    """Load the source manifest JSON."""
    if not MANIFEST_PATH.exists():
        print(f"ERROR: manifest not found: {MANIFEST_PATH}")
        sys.exit(1)
    with open(MANIFEST_PATH) as fh:
        return json.load(fh)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch direct TF-binding data for GRN Atlas species."
    )
    parser.add_argument(
        "--species",
        type=str,
        default=None,
        help="Comma-separated species to fetch (default: all). "
             "E.g. --species human,mouse",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_sources",
        help="List available sources and exit.",
    )
    args = parser.parse_args()

    manifest = load_manifest()
    sources = manifest["sources"]

    # Filter by species if requested
    if args.species:
        requested = {s.strip().lower() for s in args.species.split(",")}
        sources = [s for s in sources if s["species"].lower() in requested]
        if not sources:
            print(f"No sources found for species: {args.species}")
            print(f"Available species: {sorted(set(s['species'] for s in manifest['sources']))}")
            sys.exit(1)

    if args.list_sources:
        print("Available direct binding data sources:")
        print(f"{'Name':<20} {'Species':<12} {'Format':<16} {'Description'}")
        print("-" * 80)
        for s in sources:
            peak_note = " [needs peak calling]" if s.get("requires_peak_calling") else ""
            print(f"{s['name']:<20} {s['species']:<12} {s['format']:<16} "
                  f"{s.get('description', '')}{peak_note}")
        return

    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching direct binding data for GRN Atlas")
    print(f"Output directory: {DATA_DIR}")
    print(f"Sources to fetch: {len(sources)}")
    print()

    summary = {}
    for source_entry in sources:
        name = source_entry["name"]
        species = source_entry["species"]
        fmt = source_entry["format"]
        label = f"{name} ({species})"

        print(f"--- {label} ---")

        handler = FORMAT_HANDLERS.get(fmt)
        if handler is None:
            print(f"  WARNING: unknown format '{fmt}', skipping")
            summary[label] = 0
            continue

        try:
            n_edges = handler(source_entry, force=args.force)
            summary[label] = n_edges
        except Exception as exc:
            print(f"  ERROR: {exc}")
            summary[label] = 0

        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = 0
    for label, count in summary.items():
        status = f"{count:>10,} edges" if count > 0 else "    FAILED"
        print(f"  {label:<40} {status}")
        total += count
    print(f"  {'TOTAL':<40} {total:>10,} edges")
    print()

    if total == 0:
        print("No edges were fetched. Check the warnings above.")
        print("Some sources may require manual download or peak calling.")
        sys.exit(1)


if __name__ == "__main__":
    main()
