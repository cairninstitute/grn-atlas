"""Single source of truth for data provenance + methods, exposed via the API and
consumed by the frontend. Keeps citations, versions, and analysis parameters in
one place so exports are reproducible and citable."""

ATLAS_VERSION = "1.0.0"

# Analysis parameters that affect derived values (kept in sync with the scripts).
METHODS = {
    "promoter_window": "TSS −2000 / +500 bp (strand-aware)",
    "gene_body_window": "TSS → TES (full transcribed region)",
    "motif_scan": ("JASPAR 2026 plant PWMs scanned with a log-odds model against a "
                   "uniform 0.25 background; exact discretised score-distribution "
                   "p-value < 1e-4"),
    "tf_motif_assignment": ("TF→motif by protein-sequence homology (BLASTp) to the "
                            "JASPAR matrix TF, merged with symbol/synonym matches"),
    "inferred_edges": ("Regulatory networks projected across plant species through PLAZA/BLAST "
                       "orthology; source species and confidence penalty retained per edge"),
    "perturbation_sign_consensus": ("Experiment-level gain- and loss-of-function responses are "
                                    "orientation-normalized, aggregated by independent experiment, "
                                    "and retained only with direct binding support or replication"),
    "regulator_identification": "BLASTp vs characterised regulator proteins (best hit, %id + coverage)",
    "enrichment": "hypergeometric over-representation with Benjamini–Hochberg FDR",
    "coordinate_systems": ("gene coordinates on each species' atlas assembly (GFF 1-based); "
                           "sequence-context windows/sites on the ingest assembly (BED 0-based)"),
}

EVIDENCE_LAYERS = {
    "direct_signed": "Direct TF-target evidence with an activation or repression sign",
    "direct_unsigned": "Direct TF binding or regulation evidence without a defensible sign",
    "perturbation_signed": "Context-specific expression response after regulator perturbation",
    "causal_signaling": "Directed causal signaling relation; not necessarily TF-DNA regulation",
    "orthology_transferred": "Regulatory relation projected from another species through orthology",
    "annotation": "Gene, genome, pathway, trait, or sequence annotation",
    "method": "Software or reference model used to derive an atlas result",
}

DERIVED_SOURCE_LABELS = {
    "Perturbation sign consensus": "method:perturbation_sign_consensus",
}

# Data sources with citations. `key` is the BibTeX cite key.
SOURCES = [
    {"key": "trrust2", "name": "TRRUST v2", "version": "v2", "source_labels": ["TRRUST"],
     "evidence_layers": ["direct_signed"],
     "provides": "Human TF–target regulatory interactions (literature-curated, with PubMed IDs)",
     "authors": "Han et al.", "year": 2018, "journal": "Nucleic Acids Research", "volume": "46", "pages": "D380",
     "doi": "10.1093/nar/gkx1013", "url": "https://www.grnpedia.org/trrust/"},
    {"key": "dorothea", "name": "DoRothEA", "version": "OmniPath snapshot",
     "source_labels": ["DoRothEA"], "evidence_layers": ["direct_signed"],
     "provides": "Human and mouse signed TF-target prior knowledge (confidence A/B loaded)",
     "authors": "Garcia-Alonso et al.", "year": 2019, "journal": "Genome Research", "volume": "29", "pages": "1363",
     "doi": "10.1101/gr.240663.118", "url": "https://saezlab.github.io/dorothea/"},
    {"key": "collectri", "name": "CollecTRI", "version": "OmniPath current",
     "source_labels": ["CollecTRI"], "evidence_layers": ["direct_signed"],
     "provides": "Expanded signed human TF-target prior knowledge with source-level references",
     "authors": "Muller-Dott et al.", "year": 2023, "journal": "Nucleic Acids Research", "volume": "51", "pages": "10934",
     "doi": "10.1093/nar/gkad841", "url": "https://github.com/saezlab/CollecTRI"},
    {"key": "signor", "name": "SIGNOR", "version": "October 2026",
     "source_labels": ["SIGNOR"], "evidence_layers": ["direct_signed", "causal_signaling"],
     "provides": "Human and mouse causal relations; only the transcriptional subset enters the TF-target evidence layer",
     "authors": "Licata et al.", "year": 2020, "journal": "Nucleic Acids Research", "volume": "48", "pages": "D504",
     "doi": "10.1093/nar/gkz949", "url": "https://signor.uniroma2.it/"},
    {"key": "plantregmap", "name": "PlantRegMap / PlantTFDB", "version": "2019",
     "source_labels": ["PlantRegMap"], "evidence_layers": ["direct_unsigned", "direct_signed"],
     "provides": "Plant TF-target regulation used for Arabidopsis, tomato, petunia, potato, rice, and transfer sources",
     "authors": "Tian et al.", "year": 2020, "journal": "Nucleic Acids Research", "volume": "48", "pages": "D1104",
     "doi": "10.1093/nar/gkz1020", "url": "https://plantregmap.gao-lab.org/"},
    {"key": "atrm", "name": "Arabidopsis Transcriptional Regulatory Map", "version": "download snapshot",
     "source_labels": ["ATRM"], "evidence_layers": ["direct_signed"],
     "provides": "Literature-curated Arabidopsis activation and repression labels",
     "authors": "Jin et al.", "year": 2015, "journal": "Molecular BioSystems", "volume": "11", "pages": "178",
     "doi": "10.1039/C4MB00532C", "url": "http://atrm.cbi.pku.edu.cn/"},
    {"key": "agris", "name": "AGRIS / AtRegNet", "version": "2019-03-11",
     "source_labels": ["AGRIS AtRegNet", "AGRIS AtRegNet expanded"],
     "evidence_layers": ["direct_signed", "direct_unsigned"],
     "provides": "Arabidopsis TF-target regulation; the atlas external layer retains confirmed direct signed records",
     "authors": "Yilmaz et al.", "year": 2011, "journal": "Nucleic Acids Research", "volume": "39", "pages": "D1118",
     "doi": "10.1093/nar/gkq1120", "url": "https://agris-knowledgebase.org/"},
    {"key": "plantcistrome", "name": "Plant Cistrome DAP-seq", "version": "GSE60143",
     "source_labels": ["DAP-seq"], "evidence_layers": ["direct_unsigned"],
     "provides": "Genome-wide Arabidopsis TF binding evidence from DAP-seq",
     "authors": "O'Malley et al.", "year": 2016, "journal": "Cell", "volume": "165", "pages": "1280",
     "doi": "10.1016/j.cell.2016.04.038", "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE60143"},
    {"key": "connectf", "name": "ConnecTF", "version": "data release v1",
     "source_labels": ["ConnecTF", "connectf_target", "ConnecTF experiment evidence"],
     "evidence_layers": ["direct_unsigned", "perturbation_signed"],
     "provides": "Arabidopsis and rice TF binding and TF-perturbation expression evidence",
     "authors": "Brooks et al.", "year": 2021, "journal": "Plant Physiology", "volume": "185", "pages": "49",
     "doi": "10.1093/plphys/kiaa012", "url": "https://connectf.org/"},
    {"key": "knocktf2", "name": "KnockTF 2.0", "version": "2.0",
     "source_labels": ["KnockTF", "knocktf"], "evidence_layers": ["perturbation_signed"],
     "provides": "Context-specific TF knockdown and knockout differential-expression observations",
     "authors": "Feng et al.", "year": 2024, "journal": "Nucleic Acids Research", "volume": "52", "pages": "D183",
     "doi": "10.1093/nar/gkad1006", "url": "https://www.licpathway.net/KnockTF/"},
    {"key": "expressionatlas", "name": "Expression Atlas", "version": "reviewed manifest",
     "source_labels": ["Expression Atlas reviewed perturbations"],
     "source_label_prefixes": ["ExpressionAtlas:"],
     "evidence_layers": ["perturbation_signed"],
     "provides": "Manually reviewed regulator-perturbation contrasts with context and effect direction",
     "authors": "Papatheodorou et al.", "year": 2020, "journal": "Nucleic Acids Research",
     "volume": "48", "pages": "D77", "doi": "10.1093/nar/gkz947",
     "license": "EMBL-EBI terms", "url": "https://www.ebi.ac.uk/gxa/"},
    {"key": "chipatlas", "name": "ChIP-Atlas", "version": "live target-gene index",
     "source_labels": ["ChIP-Atlas"], "evidence_layers": ["direct_unsigned"],
     "provides": "Uniformly processed ChIP-seq target-gene occupancy evidence",
     "authors": "Oki et al.", "year": 2018, "journal": "EMBO Reports",
     "volume": "19", "pages": "e46255", "doi": "10.15252/embr.201846255",
     "license": "CC-BY-4.0", "url": "https://chip-atlas.org/target_genes"},
    {"key": "pcbase2", "name": "PCBase 2.0", "version": "2.0",
     "source_labels": ["PCBase 2.0"], "evidence_layers": ["direct_unsigned"],
     "provides": "Plant ChIP-seq peak evidence admitted only after assembly review",
     "authors": "Chow et al.", "year": 2019, "journal": "Nucleic Acids Research",
     "volume": "47", "pages": "D1155", "doi": "",
     "license": "source terms", "url": "https://pcbase.itps.ncku.edu.tw/pcbase2/"},
    {"key": "tflink", "name": "TFLink", "version": "1.0 small-scale",
     "source_labels": ["TFLink small-scale"], "evidence_layers": ["direct_unsigned"],
     "provides": "Literature-backed human and mouse TF-target evidence from small-scale experiments",
     "authors": "Liska et al.", "year": 2022, "journal": "Database",
     "volume": "2022", "pages": "baac083", "doi": "10.1093/database/baac083",
     "license": "freely available; upstream source attribution retained",
     "url": "https://tflink.net/download/"},
    {"key": "atlasliterature", "name": "GRN Atlas literature curation", "version": "repository snapshot",
     "source_labels": ["Literature", "literature_curated"], "evidence_layers": ["direct_signed", "perturbation_signed"],
     "provides": "Manually curated signed plant regulatory interactions with publication identifiers",
     "authors": "CAIRN Institute", "year": 2026, "journal": "", "volume": "", "pages": "", "doi": "",
     "url": "https://www.cairninstitute.com/"},
    {"key": "oma", "name": "OMA (Orthologous MAtrix)", "version": "2021",
     "provides": "Genomic coordinates and cross-species orthologs (human, mouse, Arabidopsis)",
     "authors": "Altenhoff et al.", "year": 2021, "journal": "Nucleic Acids Research", "volume": "49", "pages": "D373",
     "doi": "10.1093/nar/gkaa1007", "url": "https://omabrowser.org/"},
    {"key": "plaza", "name": "PLAZA Dicots 5", "version": "5",
     "source_labels": ["Inferred:Arabidopsis", "Inferred:Potato", "Inferred:Tobacco"],
     "evidence_layers": ["orthology_transferred", "annotation"],
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
    {"key": "jaspar2026", "name": "JASPAR 2026", "version": "2026",
     "source_labels": ["JASPAR2026"],
     "provides": "Plant TF binding motif matrices (PWMs) for the promoter scan",
     "authors": "JASPAR Consortium", "year": 2026, "journal": "", "volume": "", "pages": "",
     "doi": "", "url": "https://jaspar.elixir.no/"},
    {"key": "jaspar2024", "name": "JASPAR 2024", "version": "2024",
     "source_labels": ["JASPAR2024"],
     "provides": "Historical plant TF binding motif matrices retained on previously generated scans",
     "authors": "Rauluseviciute et al.", "year": 2024, "journal": "Nucleic Acids Research",
     "volume": "52", "pages": "D174", "doi": "10.1093/nar/gkad1059",
     "url": "https://jaspar.elixir.no/"},
    {"key": "mygene", "name": "mygene.info", "version": "v3",
     "provides": "Human/mouse gene names, identifiers, and GO annotations",
     "authors": "Xin et al.", "year": 2016, "journal": "Genome Biology", "volume": "17", "pages": "91",
     "doi": "10.1186/s13059-016-0953-9", "url": "https://mygene.info/"},
    {"key": "blast", "name": "NCBI BLAST+", "version": "2.17.0",
     "provides": "Sequence-homology regulator identification and TF→motif assignment",
     "authors": "Camacho et al.", "year": 2009, "journal": "BMC Bioinformatics", "volume": "10", "pages": "421",
     "doi": "10.1186/1471-2105-10-421", "url": "https://blast.ncbi.nlm.nih.gov/"},
]


def source_label_map():
    """Map labels stored in atlas tables to their canonical manifest source."""
    external = {
        label: source["key"]
        for source in SOURCES
        for label in source.get("source_labels", [])
    }
    return {**external, **DERIVED_SOURCE_LABELS}


def source_key_for_label(label: str):
    mapped = source_label_map().get(label)
    if mapped:
        return mapped
    return next((
        source["key"] for source in SOURCES
        for prefix in source.get("source_label_prefixes", [])
        if label.startswith(prefix)
    ), None)


def manifest():
    from datetime import datetime
    return {"atlas_version": ATLAS_VERSION, "generated": datetime.utcnow().isoformat() + "Z",
            "methods": METHODS, "evidence_layers": EVIDENCE_LAYERS,
            "source_label_map": source_label_map(), "sources": SOURCES}


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
