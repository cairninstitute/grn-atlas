#!/usr/bin/env python3
"""Fetch and normalize the Arabidopsis PlantRegMap and ATRM source files.

The atlas previously depended on two manually copied, gitignored TSV files. This
script recreates both from their public upstream downloads using only the Python
standard library.
"""

import argparse
import csv
import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "external_sources" / "arabidopsis_regulation"
PLANTREGMAP_URL = (
    "https://plantregmap.gao-lab.org/download_ftp.php?filepath="
    "08-download%2FArabidopsis_thaliana%2Fbinding%2Fregulation_merged_Ath.txt"
)
ATRM_URL = "https://atrm.gao-lab.org/for_download/Regulations_in_ATRM.xlsx"
USER_AGENT = "grn-atlas-data-build/1.0"

# These six literature-supported flavonoid edges were part of the atlas release
# input but are absent from PlantRegMap's merged export. Keep them explicit so a
# clean build reproduces the release network rather than relying on a local TSV.
ATLAS_SUPPLEMENT = (
    ("AT1G56650", "AT4G22880"),
    ("AT1G56650", "AT4G22870"),
    ("AT1G66390", "AT4G22880"),
    ("AT1G66390", "AT5G42800"),
    ("AT3G62610", "AT4G22880"),
    ("AT2G47460", "AT4G22880"),
)
XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, path: Path, force: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return path
    partial = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    partial.replace(path)
    return path


def plantregmap_confidence(evidence: str) -> float | None:
    literature = "literature" in evidence
    chip = "ChIP-seq" in evidence
    functional = "FunTFBS" in evidence
    if not (literature or chip or functional):
        return None
    if literature and (chip or functional):
        return 0.95
    if literature:
        return 0.90
    if chip and functional:
        return 0.85
    if chip:
        return 0.80
    return 0.65


def normalize_plantregmap(source: Path, destination: Path) -> int:
    edges = {}
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            tf, target, evidence = parts[0], parts[2], parts[4]
            confidence = plantregmap_confidence(evidence)
            if confidence is None:
                continue
            edges[(tf, target)] = ("regulation", confidence, evidence)
    for tf, target in ATLAS_SUPPLEMENT:
        edges.setdefault((tf, target), ("regulation", 0.85, "literature"))

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        for (tf, target), (regulation, confidence, evidence) in edges.items():
            writer.writerow((tf, target, regulation, f"{confidence:.2f}", evidence))
    return len(edges)


def column_index(cell_reference: str) -> int:
    letters = re.match(r"[A-Z]+", cell_reference).group(0)
    value = 0
    for letter in letters:
        value = value * 26 + ord(letter) - ord("A") + 1
    return value - 1


def read_xlsx_rows(path: Path):
    with ZipFile(path) as archive:
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = [
            "".join(node.text or "" for node in item.iter(f"{{{XML_NS}}}t"))
            for item in shared_root
        ]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        for row in sheet.iter(f"{{{XML_NS}}}row"):
            values = {}
            for cell in row.findall(f"{{{XML_NS}}}c"):
                value_node = cell.find(f"{{{XML_NS}}}v")
                value = "" if value_node is None else value_node.text or ""
                if cell.get("t") == "s" and value:
                    value = shared[int(value)]
                values[column_index(cell.get("r"))] = value
            if values:
                yield [values.get(index, "") for index in range(max(values) + 1)]


def normalize_atrm(source: Path, destination: Path) -> int:
    rows = list(read_xlsx_rows(source))
    if not rows or rows[0][:5] != [
        "TF ID", "Target ID", "TF alias", "Target alias", "Activate/Repress"
    ]:
        raise ValueError("Unexpected ATRM workbook format")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\r\n")
        writer.writerow(rows[0])
        for row in rows[1:]:
            writer.writerow(row + [""] * (len(rows[0]) - len(row)))
    return len(rows) - 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--force", action="store_true", help="Refresh upstream downloads")
    args = parser.parse_args()

    merged = download(PLANTREGMAP_URL, args.cache_dir / "regulation_merged_Ath.txt", args.force)
    workbook = download(ATRM_URL, args.cache_dir / "Regulations_in_ATRM.xlsx", args.force)
    plant_count = normalize_plantregmap(merged, args.output_dir / "regulation_arabidopsis.tsv")
    atrm_count = normalize_atrm(workbook, args.output_dir / "atrm_regulations.tsv")
    report = {
        "plantregmap": {"url": PLANTREGMAP_URL, "sha256": sha256(merged), "records": plant_count},
        "atrm": {"url": ATRM_URL, "sha256": sha256(workbook), "records": atrm_count},
    }
    (args.output_dir / "arabidopsis_regulation_fetch.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
