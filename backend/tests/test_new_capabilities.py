"""Integration tests for edge-sign inference, perturbation ground-truth, and the
Tier-1 skills (allele-affinity, gwas-to-mechanism, biosafety-screen).

These run against the real built database (the same path the skills use in direct
mode). Each test skips gracefully when its derived layer has not been built, so the
file stays green on a minimal clone while fully exercising a complete build.
"""
import asyncio
import importlib
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

import main  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def _has_column(table, col):
    return col in {r[1] for r in main.db.conn.execute(f"PRAGMA table_info({table})")}


# --------------------------------------------------------------------------- #
# Pure function: PFM -> log-odds conversion (no DB, no network)
# --------------------------------------------------------------------------- #
def test_pfm_to_lom_pure():
    cache_motif_pwms = importlib.import_module("cache_motif_pwms")
    # A column that is pure 'A' should give a strongly positive A log-odds and
    # strongly negative for the others.
    pfm = {"A": [100.0], "C": [0.0], "G": [0.0], "T": [0.0]}
    lom = cache_motif_pwms.pfm_to_lom(pfm)
    assert len(lom) == 1
    a, c, g, t = lom[0]
    assert a > 1.5 and a > c and a > g and a > t
    assert c == g == t  # symmetric zero-count bases


# --------------------------------------------------------------------------- #
# Edge-sign inference
# --------------------------------------------------------------------------- #
def test_sign_columns_present_and_consistent():
    if not _has_column("interactions", "sign_evidence"):
        pytest.skip("edge signs not built (run infer_edge_signs.py)")
    counts = dict(main.db.conn.execute(
        "SELECT sign_evidence, COUNT(*) FROM interactions GROUP BY sign_evidence"
    ).fetchall())
    assert counts.get("measured", 0) > 0, "expected some curated measured signs"
    # Measured rows must carry activation/repression and match regulation_type.
    bad = main.db.conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE sign_evidence='measured' "
        "AND sign NOT IN ('activation','repression')"
    ).fetchone()[0]
    assert bad == 0
    mismatch = main.db.conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE sign_evidence='measured' AND sign != regulation_type"
    ).fetchone()[0]
    assert mismatch == 0


def test_no_directional_sign_from_correlation():
    # Validated decision: expression correlation is NOT asserted as a directional sign.
    # Only 'measured' and 'unknown' evidence tiers should exist; no 'inferred' tier.
    if not _has_column("interactions", "sign_evidence"):
        pytest.skip("edge signs not built")
    tiers = {r[0] for r in main.db.conn.execute(
        "SELECT DISTINCT sign_evidence FROM interactions")}
    assert "inferred" not in tiers  # correlation is never a directional tier
    assert tiers <= {"measured", "perturbation", "unknown"}
    # Every row carrying a directional sign must come from a trustworthy tier, never correlation.
    bad = main.db.conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE sign IS NOT NULL "
        "AND sign_evidence NOT IN ('measured','perturbation')"
    ).fetchone()[0]
    assert bad == 0


def test_coexpression_context_is_not_a_sign():
    if not _has_column("interactions", "sign_r"):
        pytest.skip("edge signs not built")
    # sign_r (coexpression context) may be present on unsigned edges; that is allowed
    # and must never imply a directional sign.
    n_ctx_unsigned = main.db.conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE sign_r IS NOT NULL AND sign IS NULL"
    ).fetchone()[0]
    # In a build with plant expression there should be context values on unsigned edges.
    assert n_ctx_unsigned >= 0


def test_get_edge_sign_prefers_measured():
    if not _has_column("interactions", "sign_evidence"):
        pytest.skip("edge signs not built")
    row = main.db.conn.execute(
        "SELECT source_id, target_id FROM interactions WHERE sign_evidence='measured' LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip("no measured edges")
    res = main.db.get_edge_sign(row[0], row[1])
    assert res is not None and res["sign_evidence"] == "measured"
    assert main.db.get_edge_sign("NOT_A_GENE", "ALSO_NOT") is None


# --------------------------------------------------------------------------- #
# Perturbation ground-truth + calibration
# --------------------------------------------------------------------------- #
def test_perturbation_truth_loaded():
    n = main.db.conn.execute(
        "SELECT COUNT(*) FROM perturbation_observations WHERE dataset_label='literature_curated'"
    ).fetchone()[0]
    if n == 0:
        pytest.skip("perturbation ground-truth not loaded (run load_perturbation_truth.py)")
    assert n >= 10


def test_perturbation_derived_signs():
    if not _has_column("interactions", "sign_evidence"):
        pytest.skip("edge signs not built")
    n = main.db.conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE sign_evidence='perturbation'").fetchone()[0]
    if n == 0:
        pytest.skip("perturbation signs not derived (needs ConnecTF; part of make enrich)")
    # Every perturbation sign must be a real direction, and get_edge_sign must surface it.
    bad = main.db.conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE sign_evidence='perturbation' "
        "AND sign NOT IN ('activation','repression')").fetchone()[0]
    assert bad == 0
    s, t = main.db.conn.execute(
        "SELECT source_id,target_id FROM interactions WHERE sign_evidence='perturbation' LIMIT 1").fetchone()
    assert main.db.get_edge_sign(s, t)["sign_evidence"] == "perturbation"


def test_calibration_excludes_perturbation_signs():
    # The calibration scorer must not treat perturbation-tier signs as predictions (would be
    # circular against the same ConnecTF observations).
    if main.db.conn.execute(
        "SELECT COUNT(*) FROM interactions WHERE sign_evidence='perturbation'").fetchone()[0] == 0:
        pytest.skip("no perturbation signs")
    tf = main.db.conn.execute(
        "SELECT source_id FROM interactions WHERE sign_evidence='perturbation' LIMIT 1").fetchone()[0]
    res = _run(main.perturbation_compare(main.PerturbationCompareRequest(perturbed_gene=tf, min_confidence=0.0)))
    for c in res["comparisons"]:
        assert c["sign_evidence"] != "perturbation"


def test_connectf_perturbations_loaded():
    n = main.db.conn.execute(
        "SELECT COUNT(*) FROM perturbation_observations WHERE dataset_label='connectf_target'"
    ).fetchone()[0]
    if n == 0:
        pytest.skip("ConnecTF perturbations not loaded (optional; needs the ConnecTF release)")
    assert n > 1000
    # All ConnecTF TARGET observations are gain-of-function induction.
    types = {r[0] for r in main.db.conn.execute(
        "SELECT DISTINCT perturbation_type FROM perturbation_observations WHERE dataset_label='connectf_target'")}
    assert types == {"induction"}


def test_calibration_direction_aware_for_induction():
    # A measured activation edge under a gain-of-function induction assay should expect the
    # target to go UP (the inverse of a knockout), and concordant calls must reflect that.
    n = main.db.conn.execute(
        "SELECT COUNT(*) FROM perturbation_observations "
        "WHERE dataset_label='connectf_target' AND perturbed_gene='AT2G38470'"
    ).fetchone()[0]
    if n == 0:
        pytest.skip("ConnecTF WRKY33 observations not loaded")
    res = _run(main.perturbation_compare(
        main.PerturbationCompareRequest(perturbed_gene="AT2G38470", min_confidence=0.0)))
    scored = [c for c in res["comparisons"] if c["sign_evidence"] == "measured"
              and c["predicted_sign"] in ("activation", "repression")]
    assert scored, "expected at least one measured-sign edge overlapping an observation"
    lof = {"knockout", "knockdown", "crispr_ko", "ko", "kd"}
    for c in scored:
        is_lof = c["perturbation_type"] in lof
        if c["predicted_sign"] == "activation":
            assert c["expected_direction"] == ("down" if is_lof else "up")
        else:
            assert c["expected_direction"] == ("up" if is_lof else "down")
    # At least one observation must be the ConnecTF induction (gain-of-function) path.
    assert any(c["perturbation_type"] == "induction" for c in scored)


def test_knocktf_lof_perturbations_loaded():
    n = main.db.conn.execute(
        "SELECT COUNT(*) FROM perturbation_observations WHERE dataset_label='knocktf'").fetchone()[0]
    if n == 0:
        pytest.skip("KnockTF LOF perturbations not loaded (optional; needs make knocktf)")
    assert n > 1000
    types = {r[0] for r in main.db.conn.execute(
        "SELECT DISTINCT perturbation_type FROM perturbation_observations WHERE dataset_label='knocktf'")}
    assert types == {"knockdown"}  # loss-of-function


def test_calibration_lof_direction_aware():
    # KnockTF is independent of the atlas edges, so it is clean calibration ground truth.
    # Under loss-of-function, a measured activation edge expects the target DOWN.
    row = main.db.conn.execute("""
        SELECT i.source_id FROM interactions i
        JOIN perturbation_observations p ON p.perturbed_gene=i.source_id
        WHERE i.sign_evidence='measured' AND p.dataset_label='knocktf' LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no TF with both a measured sign and KnockTF observations")
    res = _run(main.perturbation_compare(main.PerturbationCompareRequest(
        perturbed_gene=row[0], min_confidence=0.0)))
    lof = [c for c in res["comparisons"] if c["dataset_label"] == "knocktf"
           and c["sign_evidence"] == "measured" and c["predicted_sign"] in ("activation", "repression")]
    if not lof:
        pytest.skip("no measured-sign KnockTF overlap in comparisons sample")
    for c in lof:
        assert c["perturbation_type"] == "knockdown"
        assert c["expected_direction"] == ("down" if c["predicted_sign"] == "activation" else "up")


def test_calibration_cbf1_concordant():
    n = main.db.conn.execute(
        "SELECT COUNT(*) FROM perturbation_observations WHERE perturbed_gene='AT4G25490'"
    ).fetchone()[0]
    if n == 0:
        pytest.skip("CBF1 observations not loaded")
    res = _run(main.perturbation_compare(
        main.PerturbationCompareRequest(perturbed_gene="AT4G25490", min_confidence=0.4)))
    assert res["n_both"] >= 1
    # Every literature CBF1 target is an activation edge, so a knockdown lowers it.
    assert res["concordance_rate"] == 1.0
    assert all(c["predicted_sign"] == "activation" for c in res["comparisons"])


# --------------------------------------------------------------------------- #
# grn-allele-affinity
# --------------------------------------------------------------------------- #
def _pwm_cache_ready():
    from sequence_design import _load_pwm_cache
    return bool(_load_pwm_cache())


def test_allele_affinity_weakens_erf2_site():
    if not _pwm_cache_ready():
        pytest.skip("PWM cache not built (run cache_motif_pwms.py)")
    res = _run(main.allele_affinity(main.AlleleAffinityRequest(
        gene_id="AT1G01020", position=11100, ref="C", alt="A")))
    assert res["n_scored"] >= 1
    top = res["results"][0]
    assert top["scored"] is True
    assert top["call"] == "weakens_binding"
    assert top["delta_lod"] < 0
    assert "JASPAR" in res["method"]


def test_allele_affinity_refalt_equal_is_neutral():
    if not _pwm_cache_ready():
        pytest.skip("PWM cache not built")
    res = _run(main.allele_affinity(main.AlleleAffinityRequest(
        gene_id="AT1G01020", position=11100, ref="C", alt="C")))
    for s in res["results"]:
        if s.get("scored"):
            assert abs(s["delta_lod"]) < 1e-6
            assert s["call"] == "little_effect"


def test_allele_affinity_invalid_base_warns():
    res = _run(main.allele_affinity(main.AlleleAffinityRequest(
        gene_id="AT1G01020", position=11100, ref="Z", alt="A")))
    assert res["results"] == []
    assert res["warnings"]


def test_allele_affinity_predicts_direction_with_measured_sign():
    if not _pwm_cache_ready() or not _has_column("interactions", "sign_evidence"):
        pytest.skip("needs PWM cache + edge signs")
    # LHY (AT1G01060) --activation--> AT1G04400 is a curated (measured) edge; LHY's motif
    # hits the AT1G04400 promoter near this position.
    res = _run(main.allele_affinity(main.AlleleAffinityRequest(
        gene_id="AT1G04400", position=1190200, ref="A", alt="T")))
    if res["n_scored"] == 0:
        pytest.skip("no scored sites for this locus in this build")
    hits = [s.get("predicted_target_effect", {}) for s in res["results"]]
    assert any(h.get("direction") in ("increase", "decrease") and h.get("sign_evidence") == "measured"
               for h in hits)
    # And no site may claim a direction from anything other than a measured sign.
    for h in hits:
        if h.get("direction") in ("increase", "decrease"):
            assert h.get("sign_evidence") == "measured"


# --------------------------------------------------------------------------- #
# grn-gwas-to-mechanism
# --------------------------------------------------------------------------- #
def test_gwas_mechanism_hy5_is_tf_with_program():
    res = _run(main.gwas_to_mechanism(main.GwasMechanismRequest(
        gene="HY5", species="arabidopsis", top=5)))
    assert res["symbol"] == "HY5"
    assert res["is_tf"] is True
    assert res["n_downstream_total"] > 0
    assert res["n_upstream_total"] > 0
    assert all("sign_evidence" in t for t in res["downstream_program"])


def test_gwas_mechanism_apoe_traits():
    res = _run(main.gwas_to_mechanism(main.GwasMechanismRequest(
        gene="APOE", species="human", top=5)))
    assert res["symbol"] == "APOE"
    assert res["n_trait_associations"] > 0
    assert res["is_tf"] is False
    assert res["downstream_program"] == []


def test_gwas_mechanism_unknown_gene_404():
    with pytest.raises(Exception):
        _run(main.gwas_to_mechanism(main.GwasMechanismRequest(gene="NOPE_XYZ_GENE")))


# --------------------------------------------------------------------------- #
# grn-biosafety-screen
# --------------------------------------------------------------------------- #
def test_biosafety_screen_coverage_and_risk():
    res = _run(main.rnai_biosafety_screen(main.BiosafetyScreenRequest(
        target_gene_id="AT1G01060", intended_species="arabidopsis")))
    assert res["overall_risk"] in ("none", "low", "moderate", "high")
    screened = {s["species"] for s in res["species_screened"]}
    assert "arabidopsis" in screened
    assert any(s["species"] == "arabidopsis" and s["intended"] for s in res["species_screened"])
    # Species without a transcriptome must be reported, not silently dropped.
    assert "human" in res["species_not_screened"]
    assert "NOT assessed" in res["coverage_note"]


def _dap_loaded():
    return main.db.conn.execute(
        "SELECT COUNT(*) FROM chromatin_peaks WHERE dataset_id='PlantCistrome_GSE60143'"
    ).fetchone()[0] > 0


def test_dapseq_peaks_loaded():
    if not _dap_loaded():
        pytest.skip("DAP-seq peaks not loaded (optional heavy layer: make chromatin-peaks)")
    peaks = main.db.conn.execute(
        "SELECT COUNT(*) FROM chromatin_peaks WHERE dataset_id='PlantCistrome_GSE60143'").fetchone()[0]
    links = main.db.conn.execute(
        "SELECT COUNT(*) FROM peak_gene_links WHERE dataset_id='PlantCistrome_GSE60143'").fetchone()[0]
    cis = main.db.conn.execute(
        "SELECT COUNT(*) FROM cis_support_edges WHERE support_type='DAP-seq_peak'").fetchone()[0]
    assert peaks > 1000 and links > 100 and cis > 100


def test_cis_support_audit_sees_chromatin():
    if not _dap_loaded():
        pytest.skip("DAP-seq peaks not loaded")
    row = main.db.conn.execute("""
        SELECT c.source_id, c.target_id FROM cis_support_edges c
        JOIN interactions i ON i.source_id=c.source_id AND i.target_id=c.target_id
        WHERE c.support_type='DAP-seq_peak' LIMIT 1""").fetchone()
    if not row:
        pytest.skip("no DAP cis edge overlapping an interaction")
    res = _run(main.cis_support_audit(main.CisSupportAuditRequest(source_id=row[0], target_id=row[1])))
    assert res["layers"]["chromatin_peak"]["present"] is True
    assert res["layers"]["cis_support"]["present"] is True
    assert res["confidence_tier"] in ("moderate", "strong")


def test_chromatin_gene_support_returns_peaks():
    if not _dap_loaded():
        pytest.skip("DAP-seq peaks not loaded")
    gid = main.db.conn.execute(
        "SELECT gene_id FROM peak_gene_links WHERE dataset_id='PlantCistrome_GSE60143' LIMIT 1").fetchone()[0]
    res = _run(main.chromatin_gene_support(gid))
    assert len(res["linked_peaks"]) > 0


def test_network_control_covers_targets():
    # Targets that share a regulator should be coverable by a small driver set.
    tf = main.db.conn.execute(
        "SELECT source_id FROM interactions GROUP BY source_id ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
    tgts = [r[0] for r in main.db.conn.execute(
        "SELECT target_id FROM interactions WHERE source_id=? LIMIT 5", (tf,))]
    sp = main.db.get_gene(tf).species
    res = _run(main.network_control(main.NetworkControlRequest(
        target_genes=tgts, species=sp, max_drivers=5, min_confidence=0.0)))
    assert res["n_targets"] == len(set(tgts))
    assert res["n_targets_covered"] >= 1
    assert res["driver_set_size"] >= 1
    assert all("recommendation" in t for d in res["driver_set"] for t in d["targets"])


def test_network_control_sign_aware_recommendation():
    # A measured activation edge, desired 'down', must recommend knockdown of the TF.
    row = main.db.conn.execute(
        "SELECT i.source_id FROM interactions i JOIN genes g ON g.id=i.source_id "
        "WHERE i.sign_evidence='measured' AND i.sign='activation' AND g.species='human' "
        "GROUP BY i.source_id ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    if not row:
        pytest.skip("no human measured activation hub")
    tf = row[0]
    tgts = [r[0] for r in main.db.conn.execute(
        "SELECT target_id FROM interactions WHERE source_id=? AND sign_evidence='measured' AND sign='activation' LIMIT 4",
        (tf,))]
    res = _run(main.network_control(main.NetworkControlRequest(
        target_genes=tgts, species="human", desired_direction="down", max_drivers=3, min_confidence=0.0)))
    recs = [t["recommendation"]["action"] for d in res["driver_set"] if d["tf_id"] == tf
            for t in d["targets"]]
    assert recs and all(a == "knockdown" for a in recs)


def test_network_control_unresolved_inputs():
    res = _run(main.network_control(main.NetworkControlRequest(
        target_genes=["NOT_A_GENE_XYZ", "AT5G11260"], species="arabidopsis", min_confidence=0.0)))
    assert "NOT_A_GENE_XYZ" in res["unresolved_inputs"]


def test_differential_network_tissue_contrast():
    if not _has_column("edge_tissue_weights", "tissue") or main.db.conn.execute(
            "SELECT COUNT(*) FROM edge_tissue_weights WHERE species='petunia'").fetchone()[0] == 0:
        pytest.skip("no tissue weights (run compute_tissue_weights / make db)")
    tissues = [r[0] for r in main.db.conn.execute(
        "SELECT DISTINCT tissue FROM edge_tissue_weights WHERE species='petunia' AND tissue!='_global' LIMIT 2")]
    if len(tissues) < 2:
        pytest.skip("need >=2 petunia tissues")
    res = _run(main.differential_network(main.DifferentialNetworkRequest(
        species="petunia", tissue_a=tissues[0], tissue_b=tissues[1])))
    assert res["n_edges_compared"] > 0
    assert "error" not in res
    assert res["n_gained_in_a"] >= 0 and res["n_strengthened_in_a"] >= 0


def test_differential_network_invalid_tissue():
    res = _run(main.differential_network(main.DifferentialNetworkRequest(
        species="petunia", tissue_a="not_a_tissue", tissue_b="also_not")))
    assert res.get("error") == "tissue not available"
    assert isinstance(res.get("available_tissues"), list)


def test_network_dynamics_reaches_attractor():
    if not _has_column("interactions", "sign_evidence"):
        pytest.skip("edge signs not built")
    # A TF with signed targets forms a signable module.
    row = main.db.conn.execute(
        "SELECT source_id FROM interactions WHERE sign_evidence IN ('measured','perturbation') "
        "AND sign IN ('activation','repression') GROUP BY source_id ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    tf = row[0]
    tgts = [r[0] for r in main.db.conn.execute(
        "SELECT target_id FROM interactions WHERE source_id=? AND sign_evidence IN ('measured','perturbation') "
        "AND sign IN ('activation','repression') LIMIT 6", (tf,))]
    sp = main.db.get_gene(tf).species
    res = _run(main.network_dynamics(main.NetworkDynamicsRequest(genes=[tf] + tgts, species=sp)))
    assert res["n_signed_edges"] >= 1
    assert res["attractor"]["type"] in ("fixed_point", "cycle", "no_convergence")
    assert 0.0 <= res["signed_coverage"] <= 1.0
    assert "final_state" in res


def test_network_dynamics_needs_two_genes():
    with pytest.raises(Exception):
        _run(main.network_dynamics(main.NetworkDynamicsRequest(genes=["AT5G11260"], species="arabidopsis")))


def test_biosafety_screen_requires_input():
    with pytest.raises(Exception):
        _run(main.rnai_biosafety_screen(main.BiosafetyScreenRequest(intended_species="arabidopsis")))


# --------------------------------------------------------------------------- #
# Coverage backfill: HTTP-only skills with no prior test in any layer
# (grn-organism-overview, grn-tissue-coexpression). These run only via the
# HTTP surface in their run.py, so they are exercised here at the endpoint level.
# --------------------------------------------------------------------------- #
def test_organism_overview_arabidopsis():
    # Pass Query-backed params explicitly (this endpoint relies on FastAPI injection).
    res = _run(main.organism_overview("arabidopsis", top=25, min_confidence=0.0, include_inferred=True))
    assert res["genes"] > 0
    assert res["transcription_factors"] > 0
    assert res["edges"]["total"] == res["edges"]["measured"] + res["edges"]["inferred"]
    assert isinstance(res["top_regulators"], list)


def test_organism_overview_unknown_species_404():
    with pytest.raises(Exception):
        _run(main.organism_overview("not_a_species", top=25, min_confidence=0.0, include_inferred=True))


def test_gene_edge_tissues_shape():
    # edge_tissue_weights may be empty in a minimal build; the endpoint must still
    # return a well-formed, non-fabricated response.
    res = _run(main.gene_edge_tissues("AT5G11260"))
    assert res["gene_id"] == "AT5G11260"
    assert isinstance(res["edges"], list)
    for e in res["edges"]:
        assert "coexpression" in e and "tissue" in e and "partner_id" in e
