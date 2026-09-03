#!/usr/bin/env python3
"""
Build human-readable display names for all genes in the database.

Most plant genes use locus IDs as their symbol (AT1G01010, Solyc02g090220.2,
PGSC0003DMG400000002, etc.), making cross-species comparisons unreadable.
This script resolves readable names from multiple sources and writes them
to the `display_name` column in the genes table.

Sources (applied in order, each filling gaps left by the previous):

  1. Own symbol     — human, mouse, and Arabidopsis genes that already have a
                      readable symbol (symbol != id).
  2. Arabidopsis    — plant genes whose Arabidopsis ortholog has a readable
     orthologs        symbol inherit that name via the orthologs table.
  3. Ensembl Plants — bulk BioMart download for Arabidopsis, tomato, and potato.
     BioMart          Adds ~3,500 Arabidopsis names and ~860 direct names.
  4. UniProt        — REST API query for Arabidopsis genes with TAIR cross-
                      references. Largest single gain (~13,000 names). Results
                      cascade to all plant species via orthologs.
  5. Description    — regex extraction of known gene symbols from the `name`
     field parsing     (description) field of remaining plant genes.
  6. Cleanup        — remove BAC clone IDs (F19K23.17, T14P4.8, etc.) that
                      passed through earlier steps.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/build_display_names.py

Prerequisites:
    - grn.sqlite3 must exist with populated genes and orthologs tables
    - Internet access for Ensembl Plants BioMart and UniProt REST API

Idempotent: safe to re-run. Existing display_name values are preserved;
only NULL entries are filled. To force a full rebuild, run:
    sqlite3 data/grn.sqlite3 "UPDATE genes SET display_name = NULL"
before running this script.

Expected coverage (as of 2026-09-02):
    human:       100%     arabidopsis: ~52%     potato: ~42%
    mouse:       100%     tomato:      ~41%     rice:   ~43%
                          petunia:     ~32%     pepper: ~40%
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

PLANT_SPECIES = ["tomato", "petunia", "potato", "rice", "pepper", "tobacco"]

# Generic protein domain / family terms that look like gene symbols but aren't
BLACKLIST = {
    "RING", "RLK", "LRR", "AP2", "NAD", "ATP", "DNA", "RNA", "CDS",
    "ABC", "GTP", "UDP", "GDP", "ADP", "FAD", "SEC", "SAM", "GMP",
    "TF", "GFP", "MYB", "SET", "MAD", "CYP", "HSP", "LEA", "DUF",
    "ARM", "PHD", "WD40", "LATE", "Late", "ERF", "NAC", "ZIP", "HD",
    "RNI", "MFS", "AAA", "PPR", "TPR", "MATE", "HMA", "NBS", "AMP",
    "CAP", "ACT", "BAM", "AXR", "PAL", "CHS", "CHI", "ANS", "DFR",
    "LAC", "PRX", "POD", "SOD", "CAT", "APX", "GR", "GST",
}

BAC_RE = re.compile(r"^[A-Z]{1,3}\d{1,3}[A-Z]\d{1,3}\.\d+$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def print_coverage(conn, label="Coverage"):
    print(f"\n=== {label} ===")
    for sp in ["arabidopsis", "tomato", "petunia", "potato", "rice",
               "pepper", "human", "mouse"]:
        total = conn.execute(
            "SELECT COUNT(*) FROM genes WHERE species = ?", (sp,)
        ).fetchone()[0]
        has_dn = conn.execute(
            "SELECT COUNT(*) FROM genes WHERE species = ? "
            "AND display_name IS NOT NULL", (sp,)
        ).fetchone()[0]
        pct = 100 * has_dn // total if total else 0
        print(f"  {sp:14s} {has_dn:>6d} / {total:>6d}  ({pct}%)")


def cascade_to_plants(conn, new_arab_names):
    """Push newly resolved Arabidopsis names to other plant species via orthologs."""
    total = 0
    for species in PLANT_SPECIES:
        rows = conn.execute("""
            SELECT o.gene_b, o.gene_a
            FROM orthologs o
            JOIN genes g ON g.id = o.gene_b AND g.species = ?
            WHERE o.species_a = 'arabidopsis' AND o.species_b = ?
            AND g.display_name IS NULL
        """, (species, species)).fetchall()

        by_plant = {}
        for plant_id, arab_id in rows:
            name = new_arab_names.get(arab_id)
            if name and (plant_id not in by_plant
                         or len(name) < len(by_plant[plant_id])):
                by_plant[plant_id] = name

        if by_plant:
            conn.executemany(
                "UPDATE genes SET display_name = ? WHERE id = ?",
                [(n, pid) for pid, n in by_plant.items()],
            )
            total += len(by_plant)
            print(f"    {species}: {len(by_plant)} cascaded")
    return total


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
    url = ("https://plants.ensembl.org/biomart/martservice?query="
           + urllib.request.quote(xml))
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


def extract_from_name_field(name, known_symbols):
    """Try to extract a readable gene name from the description field."""
    if not name or name in ("Unknown protein", "expressed protein"):
        return None
    if len(name) <= 12 and not LOCUS_RE.match(name) and name[0].isupper():
        if name.upper() not in BLACKLIST:
            return name
    for m in re.finditer(r"\b([A-Z]{2,}[A-Za-z]*\d{1,4}[A-Za-z]?)\b", name):
        candidate = m.group(1)
        if candidate.upper() in known_symbols and len(candidate) >= 3:
            return candidate
    for m in re.finditer(r"\b([A-Z]{2,}\d+[.-][A-Za-z0-9]+)\b", name):
        candidate = m.group(1)
        if candidate.upper() in known_symbols:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def stage_schema(conn):
    """Ensure the display_name column exists."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(genes)").fetchall()}
    if "display_name" not in cols:
        conn.execute("ALTER TABLE genes ADD COLUMN display_name TEXT")
        print("[schema] Added display_name column")
    else:
        print("[schema] display_name column already exists")


def stage_own_symbols(conn):
    """Set display_name from existing readable symbols (human, mouse, arabidopsis)."""
    print("\n[stage 1] Own readable symbols")
    total = 0

    # Human and mouse: symbol is already readable
    for sp in ["human", "mouse"]:
        res = conn.execute(
            "UPDATE genes SET display_name = symbol "
            "WHERE species = ? AND display_name IS NULL", (sp,)
        )
        total += res.rowcount
        print(f"  {sp}: {res.rowcount}")

    # Arabidopsis: only where symbol != id
    res = conn.execute(
        "UPDATE genes SET display_name = symbol "
        "WHERE species = 'arabidopsis' AND display_name IS NULL "
        "AND symbol != id"
    )
    total += res.rowcount
    print(f"  arabidopsis: {res.rowcount}")
    return total


def stage_arabidopsis_orthologs(conn):
    """Resolve plant gene names via Arabidopsis orthologs."""
    print("\n[stage 2] Arabidopsis ortholog cascade")
    arab_symbols = {}
    for gid, sym in conn.execute(
        "SELECT id, display_name FROM genes "
        "WHERE species = 'arabidopsis' AND display_name IS NOT NULL"
    ):
        arab_symbols[gid] = sym

    total = 0
    for species in PLANT_SPECIES:
        plant_genes = set()
        for (gid,) in conn.execute(
            "SELECT id FROM genes WHERE species = ? AND display_name IS NULL",
            (species,)
        ):
            plant_genes.add(gid)

        if not plant_genes:
            continue

        ortho_map = {}
        rows = conn.execute(
            "SELECT gene_a, gene_b FROM orthologs "
            "WHERE species_a = 'arabidopsis' AND species_b = ?",
            (species,),
        ).fetchall()
        for arab_id, plant_id in rows:
            if plant_id in plant_genes and arab_id in arab_symbols:
                existing = ortho_map.get(plant_id)
                candidate = arab_symbols[arab_id]
                if existing is None or len(candidate) < len(existing):
                    ortho_map[plant_id] = candidate

        if ortho_map:
            conn.executemany(
                "UPDATE genes SET display_name = ? WHERE id = ?",
                [(n, pid) for pid, n in ortho_map.items()],
            )
            total += len(ortho_map)
        print(f"  {species}: {len(ortho_map)}/{len(plant_genes)}")
    return total


def stage_ensembl_biomart(conn):
    """Fetch gene names from Ensembl Plants BioMart."""
    print("\n[stage 3] Ensembl Plants BioMart")

    configs = {
        "arabidopsis": ("athaliana_eg_gene", ""),
        "tomato": ("slgca000188115v5cm_eg_gene", "gene-"),
        "potato": ("stuberosum_eg_gene", ""),
    }

    new_arab_names = {}
    total = 0

    for species, (dataset, prefix) in configs.items():
        try:
            print(f"  Fetching {species}...")
            id_to_name = fetch_biomart(dataset, prefix)
            print(f"    BioMart returned {len(id_to_name)} named genes")

            genes = conn.execute(
                "SELECT id FROM genes WHERE species = ? AND display_name IS NULL",
                (species,),
            ).fetchall()

            updates = []
            for (gid,) in genes:
                if gid in id_to_name:
                    updates.append((id_to_name[gid], gid))
                    if species == "arabidopsis":
                        new_arab_names[gid] = id_to_name[gid]
                    continue
                base = gid.rsplit(".", 1)[0] if "." in gid else gid
                for eid, ename in id_to_name.items():
                    ebase = eid.rsplit(".", 1)[0] if "." in eid else eid
                    if base == ebase:
                        updates.append((ename, gid))
                        if species == "arabidopsis":
                            new_arab_names[gid] = ename
                        break

            if updates:
                conn.executemany(
                    "UPDATE genes SET display_name = ? WHERE id = ?", updates
                )
                total += len(updates)
            print(f"    {species}: {len(updates)} updated")
        except Exception as e:
            print(f"    {species}: error - {e}")

    # Cascade new Arabidopsis names to other species
    if new_arab_names:
        print("  Cascading new Arabidopsis names...")
        total += cascade_to_plants(conn, new_arab_names)

    return total


def stage_uniprot(conn):
    """Fetch Arabidopsis gene names from UniProt via TAIR cross-references."""
    print("\n[stage 4] UniProt TAIR cross-references")
    try:
        remaining = set()
        for (gid,) in conn.execute(
            "SELECT id FROM genes "
            "WHERE species = 'arabidopsis' AND display_name IS NULL"
        ):
            remaining.add(gid)
        print(f"  Arabidopsis genes without display_name: {len(remaining)}")

        url = (
            "https://rest.uniprot.org/uniprotkb/stream?"
            "query=organism_id:3702+AND+database:TAIR&"
            "fields=xref_tair,gene_names&"
            "format=tsv&size=500"
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "Darwin-GRN-Atlas/1.0"}
        )
        resp = urllib.request.urlopen(req, timeout=120)
        content = resp.read().decode()
        lines = content.strip().split("\n")
        print(f"  UniProt returned {len(lines) - 1} entries")

        uniprot_names = {}
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            tair_refs = parts[0].strip()
            gene_names = parts[1].strip()
            if not gene_names:
                continue

            primary = None
            for gn in gene_names.split():
                gn = gn.strip()
                if gn and not re.match(
                    r"^(AT[1-5CM]G\d{5}|At[1-5cm]g\d{5}|"
                    r"F\d+\.\d+|T\d+\.\d+)", gn
                ):
                    primary = gn
                    break
            if not primary or len(primary) > 20:
                continue

            for ref in tair_refs.split(";"):
                m = re.search(r"(AT[1-5CM]G\d{5})", ref.strip())
                if m:
                    at_id = m.group(1)
                    if at_id in remaining and at_id not in uniprot_names:
                        uniprot_names[at_id] = primary

        print(f"  Resolved {len(uniprot_names)} new Arabidopsis names")

        if uniprot_names:
            conn.executemany(
                "UPDATE genes SET display_name = ? WHERE id = ?",
                [(n, gid) for gid, n in uniprot_names.items()],
            )
            # Cascade
            print("  Cascading to other species...")
            cascaded = cascade_to_plants(conn, uniprot_names)
            return len(uniprot_names) + cascaded

    except Exception as e:
        print(f"  UniProt error: {e}")
    return 0


def stage_description_extraction(conn):
    """Extract gene names from description fields using pattern matching."""
    print("\n[stage 5] Description field extraction")

    known_symbols = set()
    for (sym,) in conn.execute(
        "SELECT DISTINCT symbol FROM genes "
        "WHERE symbol != id AND LENGTH(symbol) BETWEEN 2 AND 12"
    ):
        known_symbols.add(sym.upper())

    total = 0
    for species in PLANT_SPECIES:
        genes = conn.execute(
            "SELECT id, name FROM genes "
            "WHERE species = ? AND display_name IS NULL "
            "AND name IS NOT NULL AND name != id",
            (species,),
        ).fetchall()

        updates = []
        for gid, name in genes:
            extracted = extract_from_name_field(name, known_symbols)
            if extracted:
                updates.append((extracted, gid))

        if updates:
            conn.executemany(
                "UPDATE genes SET display_name = ? WHERE id = ?", updates
            )
            total += len(updates)
        if genes:
            print(f"  {species}: {len(updates)}/{len(genes)}")

    # Also try rice-specific patterns (OsWRKY22, etc.)
    rice_genes = conn.execute(
        "SELECT id, name FROM genes "
        "WHERE species = 'rice' AND display_name IS NULL AND name IS NOT NULL"
    ).fetchall()
    rice_updates = []
    for gid, name in rice_genes:
        m = re.match(r"^(Os[A-Z][A-Za-z0-9]{1,10})\b", name)
        if m:
            rice_updates.append((m.group(1), gid))
            continue
        m = re.match(r"^([A-Z]{2,}[A-Za-z]*\d+[A-Za-z]?)\b", name)
        if m and m.group(1).upper() not in BLACKLIST and len(m.group(1)) >= 3:
            rice_updates.append((m.group(1), gid))
    if rice_updates:
        conn.executemany(
            "UPDATE genes SET display_name = ? WHERE id = ?", rice_updates
        )
        total += len(rice_updates)
        print(f"  rice (extra patterns): {len(rice_updates)}")

    return total


def stage_cleanup(conn):
    """Remove display_names that are BAC clone IDs or other noise."""
    print("\n[stage 6] Cleanup")
    rows = conn.execute(
        "SELECT id, display_name FROM genes WHERE display_name IS NOT NULL"
    ).fetchall()
    to_clear = []
    for gid, dn in rows:
        if BAC_RE.match(dn):
            to_clear.append((gid,))
        elif len(dn) <= 1:
            to_clear.append((gid,))
    if to_clear:
        conn.executemany(
            "UPDATE genes SET display_name = NULL WHERE id = ?", to_clear
        )
    print(f"  Removed {len(to_clear)} bad display names")
    return len(to_clear)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    stage_schema(conn)
    conn.commit()

    n1 = stage_own_symbols(conn)
    conn.commit()

    n2 = stage_arabidopsis_orthologs(conn)
    conn.commit()

    n3 = stage_ensembl_biomart(conn)
    conn.commit()

    n4 = stage_uniprot(conn)
    conn.commit()

    n5 = stage_description_extraction(conn)
    conn.commit()

    n6 = stage_cleanup(conn)
    conn.commit()

    print_coverage(conn, "Final coverage")
    conn.close()

    print(f"\nTotal display names set: {n1 + n2 + n3 + n4 + n5}")
    print(f"Bad names removed: {n6}")


if __name__ == "__main__":
    main()
