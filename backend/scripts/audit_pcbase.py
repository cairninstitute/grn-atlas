#!/usr/bin/env python3
"""Inventory PCBase TF ChIP datasets and enforce assembly compatibility.

PCBase currently serves peak BED files but does not expose assembly identifiers in
the download table. Consequently datasets are reported as blocked for coordinate
joining until an explicit reviewed assembly/liftover manifest is supplied.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://pcbase.itps.ncku.edu.tw/pcbase2/"
SPECIES = {"Oryza_Sativa": "rice", "Solanum_lycopersicum": "tomato"}


def post(page: str, values: dict[str, str], timeout: int = 30) -> str:
    request = urllib.request.Request(
        URL + page, data=urllib.parse.urlencode(values).encode(),
        headers={"User-Agent": "grn-atlas/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def audit() -> dict:
    datasets = []
    errors = []
    for remote_species, species in SPECIES.items():
        try:
            listing = post("download_select.php", {"species": remote_species})
        except Exception as exc:
            errors.append({"species": species, "error": str(exc)})
            continue
        factors = re.findall(
            r'name="Factor" value=([^ >]+)>\s*<input type="hidden" name="type" value="TF"',
            listing,
        )
        for factor in factors:
            factor = html.unescape(factor.strip('"'))
            try:
                result = post("download_result.php", {
                    "Factor": factor, "type": "TF", "Species_name": remote_species,
                })
            except Exception as exc:
                errors.append({"species": species, "factor": factor, "error": str(exc)})
                continue
            runs = sorted(set(re.findall(r"post_file_Url\('download_file.php','([^']+)','bed'", result)))
            geo = sorted(set(re.findall(r"acc=(GSE\d+)", result)))
            datasets.append({
                "species": species, "factor": factor, "runs": runs, "geo_series": geo,
                "status": "blocked_assembly_review",
                "reason": "PCBase download metadata does not state an assembly; coordinate joins require an exact assembly declaration or liftover.",
            })
    return {
        "source": "PCBase 2.0", "source_url": URL, "datasets": datasets,
        "access_errors": errors,
        "eligible_datasets": 0,
        "boundary": "Peak files were discovered but no edge evidence was promoted across an unverified assembly boundary.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
