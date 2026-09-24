#!/usr/bin/env python3
"""Import chromatin peaks (ATAC-seq, ChIP-seq, DAP-seq) with optional peak-gene linkages. Supports BED-like format with peak type and gene annotations."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def parse_bed(bed_path: str):
    """Parse a BED-like peaks file into peaks and link dicts.

    Expected columns: chrom, start, end, peak_id, peak_type, gene_id
    gene_id is optional; if present a peak-gene link is also emitted.
    """
    peaks = []
    links = []
    with open(bed_path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("track"):
                continue
            cols = line.split("\t")
            if len(cols) < 3:
                continue
            chrom = cols[0]
            start = int(cols[1])
            end = int(cols[2])
            peak_id = cols[3] if len(cols) > 3 else f"{chrom}:{start}-{end}"
            peak_type = cols[4] if len(cols) > 4 else None
            gene_id = cols[5] if len(cols) > 5 else None

            peak = {
                "chrom": chrom,
                "start": start,
                "end": end,
                "peak_id": peak_id,
            }
            if peak_type:
                peak["peak_type"] = peak_type
            peaks.append(peak)

            if gene_id:
                links.append({
                    "peak_id": peak_id,
                    "gene_id": gene_id,
                    "link_type": "proximity",
                    "score": 0.5,
                })
    return peaks, links


def main():
    parser = argparse.ArgumentParser(description="grn-peak-import")
    common.add_common_args(parser)
    parser.add_argument("--species", default=None, help="Species")
    parser.add_argument("--peaks-file", default=None, help="Path to BED-like peaks file")
    args = parser.parse_args()

    if not args.peaks_file:
        common.output({"error": "--peaks-file is required"})
        sys.exit(1)
    if not args.species:
        common.output({"error": "--species is required"})
        sys.exit(1)

    peaks, links = parse_bed(args.peaks_file)

    payload = {
        "species": args.species,
        "peaks": peaks,
    }
    if links:
        payload["links"] = links

    if args.http:
        data = common.http_post(args.http, "/api/v1/chromatin/import-peaks", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        from main import PeakGeneImportRequest
        req = PeakGeneImportRequest(**payload)
        data = common.run_async(backend.import_peaks(req))

    common.output(data)


if __name__ == "__main__":
    main()
