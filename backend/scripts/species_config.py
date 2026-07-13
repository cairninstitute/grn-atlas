"""Central per-species onboarding config — single source of truth for the generic
ingestion scripts (fetch_seqctx.py, motif_scan.py, fetch_expression.py) and the
onboarding runbook (docs/ONBOARDING_SPECIES.md).

Adding a species = add an entry here + drop in its reference files, then run the
generic scripts + loaders. The `dahlia` entry is a prepared placeholder for the
incoming Alex/Zach data.

Fields
  status        : "loaded" | "pending"
  assembly      : assembly tag stored on windows / motif_hits
  plaza_code    : PLAZA species code (if the reference comes from PLAZA)
  gff_url       : GFF for gene models (seqctx)
  cds_url       : CDS FASTA (expression: kallisto index)
  genome_url    : genome FASTA (motif scan)
  id_style      : "strip_isoform" (rsplit '.') | "agi" (also rsplit '.')  — maps a
                  reference transcript id to the atlas gene id
  seqctx_style  : "plaza_identity" (identity crosswalk from a PLAZA-style GFF) |
                  "special" (bespoke script, e.g. tomato's SGN ITAG lift-over)
  promoter      : (upstream, downstream) bp for the promoter window
  chrom_norm    : "identity" | "tomato" (strip 'ch0*' prefix to a bare number)
  scan_edge_sql : WHERE fragment selecting (source_id, target_id) edges whose target
                  promoters get scanned for the source TF's motif
  expr_index    : kallisto index filename under data/expr/
  expr_panel    : {run_accession: [tissue, study]} curated RNA-seq panel
"""

_PLAZA_GFF = ("https://ftp.psb.ugent.be/pub/plaza/plaza_public_dicots_04_5/GFF/{code}/"
              "annotation.selected_transcript.all_features.{code}.gff3.gz")
_PLAZA_CDS = ("https://ftp.psb.ugent.be/pub/plaza/plaza_public_dicots_04_5/Fasta/"
              "cds.selected_transcript.{code}.fasta.gz")

SPECIES = {
    "petunia": {
        "status": "loaded", "assembly": "Peaxi162v1.6.2", "plaza_code": "pax",
        "gff_url": _PLAZA_GFF.format(code="pax"), "cds_url": _PLAZA_CDS.format(code="pax"),
        "genome_url": None, "id_style": "strip_isoform", "seqctx_style": "plaza_identity",
        "promoter": (2000, 500), "chrom_norm": "identity",
        "scan_edge_sql": "source_id LIKE 'Peaxi%'",
        "expr_index": "pax.idx",
        "expr_panel": {
            "SRR1585615": ["apical_shoot", "PRJNA261953"], "SRR1585635": ["flower", "PRJNA261953"],
            "SRR1585830": ["seedling", "PRJNA261953"], "SRR1585954": ["callus", "PRJNA261953"],
            "SRR1585955": ["trichome", "PRJNA261953"],
            "SRR8644905": ["corolla_lobes", "PRJNA524676"], "SRR8644913": ["corolla_lobes", "PRJNA524676"],
            "SRR8644915": ["corolla_lobes", "PRJNA524676"], "SRR8644906": ["corolla_tube", "PRJNA524676"],
            "SRR8644910": ["corolla_tube", "PRJNA524676"], "SRR8644908": ["corolla_tube", "PRJNA524676"],
            "SRR8644907": ["corolla_lobes_tz", "PRJNA524676"], "SRR8644904": ["corolla_tube_tz", "PRJNA524676"],
            "SRR12998769": ["petal_limb", "PRJNA674380"], "SRR12998762": ["petal_limb", "PRJNA674380"],
            "SRR12998768": ["petal_limb", "PRJNA674380"], "SRR12998755": ["petal_limb", "PRJNA674380"],
            "SRR12998767": ["petal_limb", "PRJNA674380"], "SRR12998766": ["petal_limb", "PRJNA674380"],
            "SRR33679195": ["bud_9wk", "PRJNA1267051"], "SRR33679192": ["bud_12wk", "PRJNA1267051"],
            "SRR33679191": ["bud_18wk", "PRJNA1267051"], "SRR33679194": ["large_bud_12wk", "PRJNA1267051"],
            "SRR33679193": ["larger_bud_18wk", "PRJNA1267051"], "SRR33679190": ["young_bud_18wk", "PRJNA1267051"],
            "SRR8930520": ["style_small", "PRJNA533335"], "SRR8930518": ["style_long", "PRJNA533335"],
            "SRR8930523": ["style_medium", "PRJNA533335"], "SRR8930526": ["style_medium", "PRJNA533335"],
        },
    },
    "tomato": {
        "status": "loaded", "assembly": "SL4.0", "plaza_code": "sly",
        "gff_url": None,  # seqctx is bespoke (SGN ITAG4.1 lift-over) -> fetch_tomato_seqctx.py
        "cds_url": _PLAZA_CDS.format(code="sly"), "genome_url": None,
        "id_style": "strip_isoform", "seqctx_style": "special",
        "promoter": (2000, 500), "chrom_norm": "tomato",
        "scan_edge_sql": "sources LIKE '%PlantRegMap%' AND source_id LIKE 'Solyc%'",
        "expr_index": "sly.idx",
        "expr_panel": {
            "DRR016684": ["leaf", "PRJDB3892"], "DRR016687": ["leaf", "PRJDB3892"],
            "DRR016686": ["fruit", "PRJDB3892"], "DRR177588": ["fruit_green", "PRJDB8570"],
            "DRR256501": ["fruit_8mm", "PRJDB10790"], "DRR092919": ["root", "PRJDB5790"],
            "DRR128403": ["root", "PRJDB8390"], "DRR092901": ["stem", "PRJDB5790"],
            "DRR092918": ["stem", "PRJDB5790"], "DRR092898": ["flower_closed", "PRJDB5790"],
            "DRR111122": ["flower_open", "PRJDB7574"], "DRR092914": ["bud_3_4mm", "PRJDB5790"],
            "DRR092915": ["bud_2mm", "PRJDB5790"], "DRR1004608": ["apex", "PRJDB11748"],
            "DRR1004609": ["apex", "PRJDB11748"], "DRR271999": ["cotyledon", "PRJDB11160"],
            "DRR272000": ["cotyledon", "PRJDB11160"], "DRR256503": ["ovary_anthesis", "PRJDB10790"],
            "DRR256504": ["ovary_anthesis", "PRJDB10790"], "DRR092900": ["leaf_mature", "PRJDB5790"],
        },
    },
    "arabidopsis": {
        "status": "loaded", "assembly": "TAIR10", "plaza_code": "ath",
        "gff_url": _PLAZA_GFF.format(code="ath"), "cds_url": _PLAZA_CDS.format(code="ath"),
        "genome_url": "https://ftp.psb.ugent.be/pub/plaza/plaza_public_dicots_04_5/Genomes/ath.con.gz",
        "id_style": "agi", "seqctx_style": "plaza_identity",
        "promoter": (2000, 500), "chrom_norm": "identity",
        "scan_edge_sql": None,  # None => scan all edges whose target is this species
        "expr_index": "ath.idx",
        "expr_panel": {
            "DRR031752": ["vegetative_shoot", "PRJDB3784"], "DRR031753": ["vegetative_shoot", "PRJDB3784"],
            "DRR031754": ["vegetative_shoot", "PRJDB3784"], "DRR031755": ["vegetative_shoot", "PRJDB3784"],
            "DRR031756": ["vegetative_shoot", "PRJDB3784"], "DRR031757": ["vegetative_shoot", "PRJDB3784"],
            "DRR031758": ["inflorescence", "PRJDB3784"], "DRR031759": ["inflorescence", "PRJDB3784"],
            "DRR031760": ["inflorescence", "PRJDB3784"], "DRR031761": ["inflorescence", "PRJDB3784"],
            "DRR031762": ["inflorescence", "PRJDB3784"], "DRR031763": ["inflorescence", "PRJDB3784"],
            "DRR016112": ["root", "PRJDB1593"], "DRR016113": ["root", "PRJDB1593"],
            "DRR070501": ["root", "PRJDB5141"], "DRR032000": ["seedling", "PRJDB3217"],
            "DRR032003": ["seedling", "PRJDB3217"], "DRR032004": ["seedling", "PRJDB3217"],
        },
    },
    # ---- Prepared placeholder for the incoming Dahlia collaboration data ----
    # Fill assembly + URLs once the G3 / NCBI BioProject genome+annotation is released.
    # Dahlia (taxid 42159) fits the anthocyanin/floral-pigmentation focus.
    "dahlia": {
        "status": "pending", "assembly": None, "plaza_code": None,
        "gff_url": None, "cds_url": None, "genome_url": None,
        "id_style": "strip_isoform", "seqctx_style": "plaza_identity",
        "promoter": (2000, 500), "chrom_norm": "identity",
        "scan_edge_sql": None, "expr_index": "dahlia.idx", "expr_panel": {},
        "notes": "Incoming: genome+GFF+RNA-seq (G3/BioProject) + ~400 GWAS cultivar runs "
                 "(Zach) for trait mapping. See memory grn-atlas-dahlia-collaboration.",
    },
}


def get(species):
    return SPECIES.get(species)
