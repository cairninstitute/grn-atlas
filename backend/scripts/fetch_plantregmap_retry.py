#!/usr/bin/env python3
"""Retry fetching data from blocked plant data sources.

Tests connectivity to PlantTFDB/PlantRegMap, GRASSIUS, and Cistrome DB.
If a source is available, downloads TF-target data.

This is a probe script — it reports what's accessible and fetches what it can.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

SOURCES = {
    "PlantTFDB": {
        "probe_urls": [
            "https://planttfdb.gao-lab.org/",
            "https://planttfdb.gao-lab.org/index.php",
            "http://planttfdb.cbi.pku.edu.cn/",
        ],
        "download_urls": {
            "arabidopsis": "https://planttfdb.gao-lab.org/download/TF_list/Ath_TF_list.txt.gz",
            "rice": "https://planttfdb.gao-lab.org/download/TF_list/Osa_TF_list.txt.gz",
            "tomato": "https://planttfdb.gao-lab.org/download/TF_list/Sly_TF_list.txt.gz",
        },
    },
    "PlantRegMap": {
        "probe_urls": [
            "https://plantregmap.gao-lab.org/",
            "https://plantregmap.gao-lab.org/regulation_download.php",
        ],
        "download_urls": {
            "arabidopsis": "https://plantregmap.gao-lab.org/download/regulation/3702_regulation_At.txt",
            "rice": "https://plantregmap.gao-lab.org/download/regulation/39947_regulation_Os.txt",
            "tomato": "https://plantregmap.gao-lab.org/download/regulation/4081_regulation_Sl.txt",
        },
    },
    "GRASSIUS": {
        "probe_urls": [
            "https://grassius.org/",
            "https://grassius.org/tfomelist.php",
        ],
        "download_urls": {},
    },
    "Cistrome_DB": {
        "probe_urls": [
            "http://cistrome.org/db/",
            "http://cistrome.org/db/#/",
            "http://dbtoolkit.cistrome.org/",
        ],
        "download_urls": {},
    },
    "ChIP-Atlas": {
        "probe_urls": [
            "https://chip-atlas.org/",
            "https://chip-atlas.dbcls.jp/data/",
        ],
        "download_urls": {
            "human_target_genes": "https://chip-atlas.dbcls.jp/data/hg38/target_genes/refFlat_TF_target.tsv.gz",
            "mouse_target_genes": "https://chip-atlas.dbcls.jp/data/mm10/target_genes/refFlat_TF_target.tsv.gz",
        },
    },
}


def probe_url(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return {"url": url, "status": resp.status, "size": len(resp.read(1024))}
    except urllib.error.HTTPError as e:
        return {"url": url, "status": e.code, "error": str(e)}
    except Exception as e:
        return {"url": url, "status": "error", "error": str(e)}


def try_download(url: str, timeout: int = 60) -> tuple[str, bytes | None]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (grn-atlas-build)"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read()
        return "ok", data
    except Exception as e:
        return str(e), None


def main():
    results = {}
    for source_name, cfg in SOURCES.items():
        print(f"\n=== {source_name} ===", flush=True)
        source_result = {"probes": [], "downloads": {}}

        for url in cfg["probe_urls"]:
            probe = probe_url(url)
            source_result["probes"].append(probe)
            status = probe.get("status", "?")
            print(f"  Probe {url}: {status}", flush=True)
            time.sleep(1)

        available = any(
            isinstance(p.get("status"), int) and 200 <= p["status"] < 400
            for p in source_result["probes"]
        )
        source_result["available"] = available

        if available and cfg.get("download_urls"):
            print(f"  {source_name} is UP, trying downloads...", flush=True)
            for label, url in cfg["download_urls"].items():
                status, data = try_download(url, timeout=120)
                if data:
                    size_mb = len(data) / (1024 * 1024)
                    source_result["downloads"][label] = {"status": "ok", "size_mb": round(size_mb, 2)}
                    print(f"    {label}: OK ({size_mb:.1f} MB)", flush=True)
                else:
                    source_result["downloads"][label] = {"status": status}
                    print(f"    {label}: FAILED ({status})", flush=True)
                time.sleep(2)
        elif not available:
            print(f"  {source_name} is DOWN — skipping downloads", flush=True)

        results[source_name] = source_result

    print(f"\n\n=== Summary ===")
    for name, r in results.items():
        status = "UP" if r["available"] else "DOWN"
        downloads = sum(1 for d in r.get("downloads", {}).values() if d.get("status") == "ok")
        total = len(r.get("downloads", {}))
        dl_str = f", {downloads}/{total} downloads" if total else ""
        print(f"  {name}: {status}{dl_str}")

    print(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
