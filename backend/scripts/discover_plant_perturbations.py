#!/usr/bin/env python3
"""Discover regulator-perturbation candidates in Expression Atlas metadata."""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.ebi.ac.uk/gxa/json/experiments"
FALLBACK_URL = "https://ftp.ebi.ac.uk/pub/databases/microarray/data/atlas/experiments.json"
SPECIES = {
    "arabidopsis": "Arabidopsis thaliana",
    "rice": "Oryza sativa",
    "tomato": "Solanum lycopersicum",
    "potato": "Solanum tuberosum",
    "pepper": "Capsicum annuum",
    "petunia": "Petunia axillaris",
    "human": "Homo sapiens",
    "mouse": "Mus musculus",
}
RECIPIENT_PLANTS = ("rice", "tomato", "potato", "pepper", "petunia")
DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "source_manifests" / "expression_atlas_reviewed.json"
PERTURBATION_TERMS = (
    "knockout", "knockdown", "mutant", "overexpress", "silenc", "crispr", "transgenic",
)
REGULATOR_PATTERNS = {
    "arabidopsis": re.compile(r"\b(?:AT[1-5CM]G\d{5}|[A-Z][A-Z0-9-]{1,15})\b"),
    "rice": re.compile(r"\b(?:Os[A-Za-z0-9-]+|[A-Za-z0-9-]+(?:TF|ZIP|MYB|NAC|WRKY)\d*)\b"),
    "tomato": re.compile(r"\b(?:Sl[A-Za-z0-9-]+|[A-Za-z0-9-]+(?:TF|ZIP|MYB|NAC|WRKY)\d*)\b"),
    "potato": re.compile(r"\b(?:St[A-Za-z0-9-]+|PGSC\w+|[A-Za-z0-9-]+(?:TF|MYB|NAC|WRKY)\d*)\b"),
    "pepper": re.compile(r"\b(?:Ca[A-Za-z0-9-]+|CA\w+|[A-Za-z0-9-]+(?:TF|MYB|NAC|WRKY)\d*)\b"),
    "petunia": re.compile(r"\b(?:Ph[A-Za-z0-9-]+|Peaxi\w+|[A-Za-z0-9-]+(?:TF|MYB|NAC|WRKY)\d*)\b"),
    "human": re.compile(r"\b[A-Z][A-Z0-9-]{1,15}\b"),
    "mouse": re.compile(r"\b[A-Z][A-Za-z0-9-]{1,15}\b"),
}


def discover(
    payload: dict,
    reviewed_accessions: set[str] | None = None,
    species_keys: tuple[str, ...] = RECIPIENT_PLANTS,
) -> dict:
    reviewed_accessions = reviewed_accessions or set()
    results = {}
    experiments = payload.get("experiments", [])
    for atlas_species in species_keys:
        scientific_name = SPECIES[atlas_species]
        candidates = []
        for experiment in experiments:
            description = experiment.get("experimentDescription", "")
            if experiment.get("species") != scientific_name:
                continue
            if experiment.get("experimentType") != "Differential":
                continue
            terms = [term for term in PERTURBATION_TERMS if term in description.lower()]
            if not terms:
                continue
            candidates.append({
                "accession": experiment.get("experimentAccession"),
                "description": description,
                "technology": experiment.get("technologyType", []),
                "assays": experiment.get("numberOfAssays"),
                "perturbation_terms": terms,
                "regulator_tokens": sorted(set(REGULATOR_PATTERNS[atlas_species].findall(description))),
                "experiment_url": (
                    "https://www.ebi.ac.uk/gxa/experiments/"
                    f"{experiment.get('experimentAccession')}/home"
                ),
                "status": ("approved_manifest_present" if experiment.get("experimentAccession")
                           in reviewed_accessions
                           else "candidate_requires_contrast_and_identifier_review"),
            })
        results[atlas_species] = candidates
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "source": "Expression Atlas experiment catalogue",
        "source_url": URL,
        "perturbatlas": {
            "status": "manual_download_review_required",
            "reason": "The public site currently exposes bulk results through file-sharing mirrors rather than a stable catalogue API.",
            "download_page": "https://perturbatlas.kratoss.site/#/download",
            "ingestion": "Normalize selected DEG tables to the grn-perturbation-import TSV contract after species and contrast review.",
        },
        "selection": "Differential experiments whose descriptions contain a genetic perturbation term",
        "limitations": [
            "Catalogue descriptions do not prove that the perturbed gene is a transcriptional regulator.",
            "Each candidate requires contrast-level review and atlas identifier mapping before ingestion.",
            "Perturbation effects belong in perturbation_signed, not direct_signed, unless direct binding is independently supported.",
        ],
        "species": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reviewed-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--include-arabidopsis", action="store_true")
    args = parser.parse_args()
    payload = None
    source_url = URL
    for source_url in (URL, FALLBACK_URL):
        try:
            request = urllib.request.Request(source_url, headers={"User-Agent": "grn-atlas/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
            break
        except Exception:
            continue
    if payload is None:
        raise RuntimeError("Expression Atlas catalogue and FTP fallback are unavailable")
    reviewed_accessions = set()
    if args.reviewed_manifest.exists():
        manifest = json.loads(args.reviewed_manifest.read_text())
        reviewed_accessions = {
            item["accession"] for item in manifest.get("contrasts", [])
            if item.get("review_status") == "approved" and item.get("accession")
        }
    species_keys = RECIPIENT_PLANTS + (("arabidopsis",) if args.include_arabidopsis else ())
    report = discover(payload, reviewed_accessions, species_keys)
    report["source_url"] = source_url
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
