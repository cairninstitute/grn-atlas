"""Targeted units for the enrichment-pipeline logic that isn't covered by the
DB/API tiers: the 3D-DNA liftover math and the annotation-version crosswalk /
protein-id -> gene-id matching."""
from fetch_plaza_data import build_lift_from_text
from fetch_tomato_seqctx import base_id as tom_base, norm_chrom as tom_norm_chrom
from blast_regulators import protein_to_gene_id


# ---------- 3D-DNA liftover ----------

# Two scaffolds; ScfA split into two fragments forms the longer super-scaffold.
FWD = (
    ">ScfA:::fragment_1 1 100\n"
    ">ScfA:::fragment_2 2 200\n"
    ">ScfB:::fragment_1 3 150\n"
    "1 2\n"       # chromosome 1 = ScfA frag1 + frag2  (len 300)
    "3\n"         # chromosome 2 = ScfB frag1          (len 150)
)


def test_lift_forward_within_fragments():
    lift, clen = build_lift_from_text(FWD, n_chroms=2)
    assert clen == {"1": 300, "2": 150}
    assert lift("ScfA", 50) == ("1", 50)      # in frag1
    assert lift("ScfA", 150) == ("1", 150)    # in frag2: chrom_off 100 + (150-100)
    assert lift("ScfB", 30) == ("2", 30)      # second super-scaffold


def test_lift_unknown_scaffold_and_range():
    lift, _ = build_lift_from_text(FWD, n_chroms=2)
    assert lift("ScfZ", 10) is None           # scaffold not in assembly


def test_lift_respects_chromosome_cap():
    lift, clen = build_lift_from_text(FWD, n_chroms=1)   # only the longest is a chromosome
    assert set(clen) == {"1"}
    assert lift("ScfA", 50) == ("1", 50)
    assert lift("ScfB", 30) is None           # unplaced when capped out


def test_lift_reverse_fragment():
    rev = (">ScfA:::fragment_1 1 100\n"
           ">ScfA:::fragment_2 2 200\n"
           "1 -2\n")                          # frag2 reverse-oriented
    lift, _ = build_lift_from_text(rev, n_chroms=1)
    # frag2 occupies scaffold [100,300); reversed on chrom: coff + (flen - off_in)
    assert lift("ScfA", 150) == ("1", 100 + (200 - 50))   # = 250
    assert lift("ScfA", 100) == ("1", 100 + 200)          # start of reversed frag = 300


# ---------- crosswalk / id matching ----------

def test_tomato_base_id_strips_version():
    assert tom_base("Solyc01g005060.2") == "Solyc01g005060"
    assert tom_base("Solyc00g160260.1") == "Solyc00g160260"


def test_base_id_links_across_annotation_versions():
    # the crosswalk matches ITAG2.4 (.2) to ITAG4.1 (.5) by shared base id
    assert tom_base("Solyc01g005010.2") == tom_base("Solyc01g005010.5")


def test_base_id_identity_for_versionless_ids():
    # petunia atlas ids carry no version -> base id is the id itself (identity crosswalk)
    assert tom_base("Peaxi162Scf00047g01225") == "Peaxi162Scf00047g01225"


def test_tomato_norm_chrom():
    assert tom_norm_chrom("SL4.0ch07") == "7"
    assert tom_norm_chrom("SL4.0ch00") == "0"


def test_protein_to_gene_id_drops_only_transcript_suffix():
    # regression for the version-suffix bug: keep the gene version, drop transcript
    assert protein_to_gene_id("Solyc10g086260.2.1") == "Solyc10g086260.2"
    assert protein_to_gene_id("Peaxi162Scf00000g00013.1") == "Peaxi162Scf00000g00013"
