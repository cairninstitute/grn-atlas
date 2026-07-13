"""Data-freshness audit (#6): compare each atlas source's loaded version against the
latest publicly available release, so users know how current the data is.

Best-effort live probes (a source that can't be checked is reported status='unknown',
never guessed). Writes a committed cache the API serves; re-run to refresh.

Output: backend/data/source_freshness.json
  {"checked": ISO-date, "sources": {key: {our_version, latest_version, status, note}}}

Usage: python backend/scripts/check_source_freshness.py
"""
import datetime
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import provenance  # noqa: E402

DATA = Path(__file__).parent.parent / "data"
OUT = DATA / "source_freshness.json"
UA = {"User-Agent": "grn-atlas-freshness/1.0"}


def _get(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def latest_plaza_dicots():
    html = _get("https://ftp.psb.ugent.be/pub/plaza/")
    if not html:
        return None
    vers = set(re.findall(r"plaza_public_dicots_([0-9_]+)", html))
    if not vers:
        return None
    # "04_5" -> (4,5); "05" -> (5,0)
    def key(v):
        parts = v.strip("_").split("_")
        return tuple(int(p) for p in parts) + (0,) * (2 - len(parts))
    best = max(vers, key=key)
    return best.strip("_").replace("_", ".").lstrip("0") or best


def latest_reactome():
    v = _get("https://reactome.org/ContentService/data/database/version")
    return v.strip() if v and v.strip().isdigit() else None


# key -> (probe callable or None, static note). our_version comes from provenance.SOURCES.
PROBES = {
    "plaza": (latest_plaza_dicots, "PLAZA dicots"),
    "plantreactome": (latest_reactome, "Reactome/Plant Reactome share a release number"),
    "gwascatalog": (None, "tracked as 'latest'; re-fetch pulls the current weekly release"),
    "jaspar2024": (None, "JASPAR 2024 is the current CORE release"),
    "trrust2": (None, "TRRUST v2 is the latest published release"),
    "oma": (None, "OMA browser updates periodically; not auto-checked"),
    "dnazoo": (None, "static assembly release"),
    "mygene": (None, "live API; always current at fetch time"),
    "ncbi": (None, "live resource"),
}


def _norm(v):
    return re.sub(r"[^0-9.]", "", str(v or "")).strip(".")


def main():
    our = {s["key"]: s.get("version") for s in provenance.SOURCES}
    out = {}
    for key, ourv in our.items():
        probe, note = PROBES.get(key, (None, ""))
        latest = probe() if probe else None
        if str(ourv).lower() in ("current", "latest"):
            status = "current"  # we always re-fetch the current release of this source
        elif latest is None:
            status = "unknown"
        else:
            status = "current" if _norm(latest) == _norm(ourv) else "stale"
        out[key] = {"our_version": ourv, "latest_version": latest,
                    "status": status, "note": note}
        print(f"  {key:16} ours={ourv!s:10} latest={latest!s:8} -> {status}")
    payload = {"checked": datetime.date.today().isoformat(), "sources": out}
    OUT.write_text(json.dumps(payload, indent=1))
    stale = [k for k, v in out.items() if v["status"] == "stale"]
    print(f"\nwrote {OUT}  (stale: {', '.join(stale) or 'none'})")


if __name__ == "__main__":
    main()
