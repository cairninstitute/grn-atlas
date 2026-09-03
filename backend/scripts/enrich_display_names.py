"""
Enrich display_name for plant genes using multiple strategies:
1. Ensembl Plants BioMart bulk download (tomato, potato, rice)
2. Extract gene names from the existing 'name' field using curated patterns
3. Match against known Arabidopsis symbols found in descriptions

Run after migrate_display_names.py.
"""
import sqlite3
import re
import urllib.request
import json
import sys

DB_PATH = "data/grn.sqlite3"

LOCUS_RE = re.compile(
    r"^(AT[1-5CM]G\d{5}|Solyc\d+g\d+|Peaxi\d+Scf\d+g\d+|"
    r"PGSC\d+DMG\d+|LOC_Os\d+g\d+|Nitab\d+g\d+|gene-)"
)

# Generic terms that look like gene symbols but aren't specific enough
BLACKLIST = {
    "RING", "RLK", "LRR", "AP2", "NAD", "ATP", "DNA", "RNA", "CDS",
    "ABC", "GTP", "UDP", "GDP", "ADP", "FAD", "SEC", "SAM", "GMP",
    "TF", "GFP", "MYB", "SET", "MAD", "CYP", "HSP", "LEA", "DUF",
    "ARM", "PHD", "WD40", "LATE", "Late", "ERF", "NAC", "ZIP", "HD",
    "RNI", "MFS", "AAA", "PPR", "TPR", "MATE", "HMA", "NBS", "AMP",
    "CAP", "ACT", "BAM", "AXR", "PAL", "CHS", "CHI", "ANS", "DFR",
    "LAC", "PRX", "POD", "SOD", "CAT", "APX", "GR", "GST",
}


def fetch_biomart(dataset, prefix_strip=""):
    """Bulk download gene names from Ensembl Plants BioMart."""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Query>
<Query virtualSchemaName="plants_mart" formatter="TSV" header="1"
       uniqueRows="1" count="0">
  <Dataset name="{dataset}" interface="default">
    <Attribute name="ensembl_gene_id" />
    <Attribute name="external_gene_name" />
    <Attribute name="uniprot_gn_symbol" />
  </Dataset>
</Query>"""
    url = "https://plants.ensembl.org/biomart/martservice?query=" + urllib.request.quote(xml)
    resp = urllib.request.urlopen(url, timeout=120)
    content = resp.read().decode()
    lines = content.strip().split("\n")

    id_to_name = {}
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        eid = parts[0].strip()
        if prefix_strip:
            eid = re.sub(prefix_strip, "", eid)
        gene_name = parts[1].strip() if len(parts) > 1 else ""
        uniprot_sym = parts[2].strip() if len(parts) > 2 else ""
        name = gene_name or uniprot_sym
        if not name or name.startswith("LOC") or len(name) > 25:
            continue
        if name.upper() in BLACKLIST:
            continue
        id_to_name[eid] = name
    return id_to_name


def extract_from_name_field(name, arab_symbols):
    """Try to extract a readable gene name from the description field."""
    if not name or name == "Unknown protein" or name == "expressed protein":
        return None

    # Strategy 1: If the entire name is short and not a locus ID, use it
    if len(name) <= 12 and not LOCUS_RE.match(name) and name[0].isupper():
        if name.upper() not in BLACKLIST:
            return name

    # Strategy 2: Look for known Arabidopsis symbols in the name
    # Match word boundaries for symbols like "MYB30", "WRKY22", "NAC010"
    for m in re.finditer(r"\b([A-Z]{2,}[A-Za-z]*\d{1,4}[A-Za-z]?)\b", name):
        candidate = m.group(1)
        if candidate.upper() in arab_symbols and len(candidate) >= 3:
            return candidate
    # Try patterns like "RAP2-4", "CYP86A4"
    for m in re.finditer(r"\b([A-Z]{2,}\d+[.-][A-Za-z0-9]+)\b", name):
        candidate = m.group(1)
        if candidate.upper() in arab_symbols:
            return candidate

    # Strategy 3: Name ends with a gene-name-like token after a space
    # e.g., "gibberellin 20-oxidase 3" won't match, but
    # "Ethylene-responsive transcription factor RAP2-4" will
    parts = name.split("(")[0].strip().split()
    if parts:
        last = parts[-1]
        if (re.match(r"^[A-Z][A-Z0-9]{2,}(?:[.-]\d+)?$", last)
                and last.upper() not in BLACKLIST
                and last.upper() in arab_symbols):
            return last

    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    # Load Arabidopsis symbol set for matching
    arab_symbols = set()
    for (sym,) in conn.execute(
        "SELECT DISTINCT symbol FROM genes WHERE species = 'arabidopsis' AND symbol != id"
    ):
        arab_symbols.add(sym.upper())
    # Also add common non-arabidopsis gene symbols
    for (sym,) in conn.execute(
        "SELECT DISTINCT symbol FROM genes WHERE symbol != id AND LENGTH(symbol) BETWEEN 2 AND 12"
    ):
        arab_symbols.add(sym.upper())
    print(f"Known gene symbols for matching: {len(arab_symbols)}")

    total_updated = 0

    # === Strategy 1: Ensembl Plants BioMart ===
    biomart_configs = {
        "tomato": ("slgca000188115v5cm_eg_gene", "gene-"),
        "potato": ("stuberosum_eg_gene", ""),
    }

    for species, (dataset, prefix) in biomart_configs.items():
        try:
            print(f"\nFetching Ensembl Plants data for {species}...")
            id_to_name = fetch_biomart(dataset, prefix)
            print(f"  Got {len(id_to_name)} named genes from BioMart")

            genes = conn.execute(
                "SELECT id FROM genes WHERE species = ? AND display_name IS NULL",
                (species,),
            ).fetchall()

            updates = []
            for (gid,) in genes:
                # Try exact match
                if gid in id_to_name:
                    updates.append((id_to_name[gid], gid))
                    continue
                # Try base ID without version
                base = gid.rsplit(".", 1)[0] if "." in gid else gid
                for eid, ename in id_to_name.items():
                    ebase = eid.rsplit(".", 1)[0] if "." in eid else eid
                    if base == ebase:
                        updates.append((ename, gid))
                        break

            if updates:
                conn.executemany(
                    "UPDATE genes SET display_name = ? WHERE id = ?", updates
                )
                total_updated += len(updates)
            print(f"  {species}: {len(updates)} genes updated from BioMart")
        except Exception as e:
            print(f"  {species}: BioMart error - {e}")

    # === Strategy 2: Rice MSU-RAP mapping ===
    # Rice uses LOC_Os IDs (MSU), try fetching RAP-DB names
    try:
        print("\nFetching rice gene names from RAP-DB...")
        url = "https://rapdb.dna.affrc.go.jp/download/archive/RAP-MSU.txt.gz"
        import gzip, io
        resp = urllib.request.urlopen(url, timeout=60)
        raw = gzip.decompress(resp.read()).decode()
        # Format: RAP_ID\tMSU_ID (LOC_Os...)
        rap_to_msu = {}
        for line in raw.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 2:
                rap_id = parts[0].strip()
                msu_id = parts[1].strip()
                if msu_id.startswith("LOC_Os"):
                    rap_to_msu[msu_id] = rap_id

        # Now get RAP gene names
        url2 = "https://rapdb.dna.affrc.go.jp/download/archive/IRGSP-1.0_representative_annotation_data.tsv.gz"
        resp2 = urllib.request.urlopen(url2, timeout=60)
        raw2 = gzip.decompress(resp2.read()).decode()
        rap_names = {}
        for line in raw2.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 3:
                rap_id = parts[0].strip()
                desc = parts[2].strip() if len(parts) > 2 else ""
                # Extract gene symbol from description
                # Many have format: "Similar to Gene_name."
                m = re.match(r"Similar to ([A-Z][A-Za-z0-9]{1,12}(?:[.-]\d+)?)\b", desc)
                if m and m.group(1).upper() not in BLACKLIST:
                    rap_names[rap_id] = m.group(1)

        rice_genes = conn.execute(
            "SELECT id FROM genes WHERE species = 'rice' AND display_name IS NULL"
        ).fetchall()

        updates = []
        for (gid,) in rice_genes:
            rap = rap_to_msu.get(gid)
            if rap and rap in rap_names:
                updates.append((rap_names[rap], gid))

        if updates:
            conn.executemany(
                "UPDATE genes SET display_name = ? WHERE id = ?", updates
            )
            total_updated += len(updates)
        print(f"  rice: {len(updates)} genes updated from RAP-DB")
    except Exception as e:
        print(f"  rice: RAP-DB error - {e}")

    # === Strategy 3: Extract from name field ===
    print("\nExtracting names from description fields...")
    for species in ["tomato", "petunia", "potato", "rice", "pepper"]:
        genes = conn.execute(
            """SELECT id, name FROM genes
               WHERE species = ? AND display_name IS NULL
               AND name IS NOT NULL AND name != id""",
            (species,),
        ).fetchall()

        updates = []
        for gid, name in genes:
            extracted = extract_from_name_field(name, arab_symbols)
            if extracted:
                updates.append((extracted, gid))

        if updates:
            conn.executemany(
                "UPDATE genes SET display_name = ? WHERE id = ?", updates
            )
            total_updated += len(updates)
        print(f"  {species}: {len(updates)}/{len(genes)} genes got names from descriptions")

    conn.commit()

    # === Summary ===
    print("\n=== Final coverage ===")
    for species in ["arabidopsis", "tomato", "petunia", "potato", "rice", "pepper", "human", "mouse"]:
        total = conn.execute(
            "SELECT COUNT(*) FROM genes WHERE species = ?", (species,)
        ).fetchone()[0]
        has_dn = conn.execute(
            "SELECT COUNT(*) FROM genes WHERE species = ? AND display_name IS NOT NULL",
            (species,),
        ).fetchone()[0]
        print(f"  {species}: {has_dn}/{total} ({100 * has_dn // total}%)")

    conn.close()
    print(f"\nTotal new display names: {total_updated}")


if __name__ == "__main__":
    main()
