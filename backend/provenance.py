"""Single source of truth for data provenance + methods, exposed via the API and
consumed by the frontend. Keeps citations, versions, and analysis parameters in
one place so exports are reproducible and citable."""

ATLAS_VERSION = "1.0.0"

# Analysis parameters that affect derived values (kept in sync with the scripts).
METHODS = {
    "promoter_window": "TSS −2000 / +500 bp (strand-aware)",
    "gene_body_window": "TSS → TES (full transcribed region)",
    "motif_scan": ("JASPAR 2024 plant PWMs scanned with a log-odds model against a "
                   "uniform 0.25 background; exact discretised score-distribution "
                   "p-value < 1e-4"),
    "tf_motif_assignment": ("TF→motif by protein-sequence homology (BLASTp) to the "
                            "JASPAR matrix TF, merged with symbol/synonym matches"),
    "inferred_edges": ("Arabidopsis regulatory network projected onto tomato/petunia "
                       "via orthology; confidence penalised ×0.7"),
    "regulator_identification": "BLASTp vs characterised regulator proteins (best hit, %id + coverage)",
    "enrichment": "hypergeometric over-representation with Benjamini–Hochberg FDR",
    "coordinate_systems": ("gene coordinates on each species' atlas assembly (GFF 1-based); "
                           "sequence-context windows/sites on the ingest assembly (BED 0-based)"),
}

# Data sources with citations. `key` is the BibTeX cite key.
SOURCES = [
    {"key": "trrust2", "name": "TRRUST v2", "version": "v2",
     "provides": "Human TF–target regulatory interactions (literature-curated, with PubMed IDs)",
     "authors": "Han et al.", "year": 2018, "journal": "Nucleic Acids Research", "volume": "46", "pages": "D380",
     "doi": "10.1093/nar/gkx1013", "url": "https://www.grnpedia.org/trrust/"},
    {"key": "plantregmap", "name": "PlantRegMap / PlantTFDB", "version": "2019",
     "provides": "Arabidopsis & tomato TF–target regulation (FunTFBS)",
     "authors": "Tian et al.", "year": 2020, "journal": "Nucleic Acids Research", "volume": "48", "pages": "D1104",
     "doi": "10.1093/nar/gkz1020", "url": "https://plantregmap.gao-lab.org/"},
    {"key": "oma", "name": "OMA (Orthologous MAtrix)", "version": "2021",
     "provides": "Genomic coordinates and cross-species orthologs (human, mouse, Arabidopsis)",
     "authors": "Altenhoff et al.", "year": 2021, "journal": "Nucleic Acids Research", "volume": "49", "pages": "D373",
     "doi": "10.1093/nar/gkaa1007", "url": "https://omabrowser.org/"},
    {"key": "plaza", "name": "PLAZA Dicots 4.5", "version": "4.5",
     "provides": "Plant gene coordinates, synteny, BHIF orthology, descriptions, GO (Arabidopsis, tomato, petunia)",
     "authors": "Van Bel et al.", "year": 2018, "journal": "Nucleic Acids Research", "volume": "46", "pages": "D1190",
     "doi": "10.1093/nar/gkx1002", "url": "https://bioinformatics.psb.ugent.be/plaza/"},
    {"key": "uniprot", "name": "UniProt / Swiss-Prot", "version": "2024",
     "provides": "Curated gene symbols for tomato (via EnsemblPlants xref) and petunia "
                 "(P. hybrida, mapped to P. axillaris loci by homology)",
     "authors": "The UniProt Consortium", "year": 2023, "journal": "Nucleic Acids Research",
     "volume": "51", "pages": "D523", "doi": "10.1093/nar/gkac1052", "url": "https://www.uniprot.org/"},
    {"key": "plantreactome", "name": "Plant Reactome (Gramene)", "version": "current",
     "provides": "Curated pathway membership for enrichment (Arabidopsis, tomato)",
     "authors": "Naithani et al.", "year": 2020, "journal": "Nucleic Acids Research", "volume": "48", "pages": "D1093",
     "doi": "10.1093/nar/gkz996", "url": "https://plantreactome.gramene.org/"},
    {"key": "gwascatalog", "name": "GWAS Catalog (EBI/NHGRI)", "version": "latest",
     "provides": "Human gene–trait associations for trait enrichment (statistical, GWAS-mapped)",
     "authors": "Sollis et al.", "year": 2023, "journal": "Nucleic Acids Research", "volume": "51", "pages": "D977",
     "doi": "10.1093/nar/gkac1010", "url": "https://www.ebi.ac.uk/gwas/"},
    {"key": "dnazoo", "name": "DNA Zoo — P. axillaris Hi-C", "version": "v1.6.2 HiC",
     "provides": "Chromosome-scale scaffolding of the P. axillaris v1.6.2 assembly",
     "authors": "Dudchenko et al.", "year": 2017, "journal": "Science", "volume": "356", "pages": "92",
     "doi": "10.1126/science.aal3327", "url": "https://www.dnazoo.org/"},
    {"key": "itag41", "name": "SGN ITAG4.1 / SL4.0", "version": "ITAG4.1",
     "provides": "Tomato SL4.0 assembly & ITAG4.1 gene models (sequence-context windows)",
     "authors": "Hosmani et al.", "year": 2019, "journal": "bioRxiv", "volume": "", "pages": "767764",
     "doi": "10.1101/767764", "url": "https://solgenomics.net/"},
    {"key": "jaspar2024", "name": "JASPAR 2024", "version": "2024",
     "provides": "Plant TF binding motif matrices (PWMs) for the promoter scan",
     "authors": "Rauluseviciute et al.", "year": 2024, "journal": "Nucleic Acids Research", "volume": "52", "pages": "D174",
     "doi": "10.1093/nar/gkad1059", "url": "https://jaspar.elixir.no/"},
    {"key": "mygene", "name": "mygene.info", "version": "v3",
     "provides": "Human/mouse gene names, identifiers, and GO annotations",
     "authors": "Xin et al.", "year": 2016, "journal": "Genome Biology", "volume": "17", "pages": "91",
     "doi": "10.1186/s13059-016-0953-9", "url": "https://mygene.info/"},
    {"key": "blast", "name": "NCBI BLAST+", "version": "2.17.0",
     "provides": "Sequence-homology regulator identification and TF→motif assignment",
     "authors": "Camacho et al.", "year": 2009, "journal": "BMC Bioinformatics", "volume": "10", "pages": "421",
     "doi": "10.1186/1471-2105-10-421", "url": "https://blast.ncbi.nlm.nih.gov/"},
]


def manifest():
    from datetime import datetime
    return {"atlas_version": ATLAS_VERSION, "generated": datetime.utcnow().isoformat() + "Z",
            "methods": METHODS, "sources": SOURCES}


def freshness():
    """Data-currency audit: each source's loaded version vs the latest available
    release (from the committed source_freshness.json cache; run
    scripts/check_source_freshness.py to refresh). Merges in each source's display
    name + url. Sources not in the cache are reported status='unknown'."""
    import json
    from pathlib import Path
    cache_path = Path(__file__).parent / "data" / "source_freshness.json"
    cache = {"checked": None, "sources": {}}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())
    fresh = cache.get("sources", {})
    rows = []
    for s in SOURCES:
        f = fresh.get(s["key"], {})
        rows.append({"key": s["key"], "name": s["name"], "url": s.get("url"),
                     "our_version": f.get("our_version", s.get("version")),
                     "latest_version": f.get("latest_version"),
                     "status": f.get("status", "unknown"), "note": f.get("note", "")})
    return {"checked": cache.get("checked"),
            "stale": [r["key"] for r in rows if r["status"] == "stale"],
            "sources": rows}


def bibtex():
    out = []
    for s in SOURCES:
        fields = [f"  title = {{{s['name']} — {s['provides']}}}",
                  f"  author = {{{s['authors']}}}",
                  f"  year = {{{s['year']}}}"]
        if s.get("journal"):
            fields.append(f"  journal = {{{s['journal']}}}")
        if s.get("volume"):
            fields.append(f"  volume = {{{s['volume']}}}")
        if s.get("pages"):
            fields.append(f"  pages = {{{s['pages']}}}")
        if s.get("doi"):
            fields.append(f"  doi = {{{s['doi']}}}")
        if s.get("url"):
            fields.append(f"  url = {{{s['url']}}}")
        out.append(f"@article{{{s['key']},\n" + ",\n".join(fields) + "\n}")
    return "\n\n".join(out) + "\n"
