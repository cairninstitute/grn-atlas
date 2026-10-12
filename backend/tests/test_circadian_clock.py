import numpy as np

import circadian_clock
import main


def test_compact_clock_has_circadian_limit_cycle():
    simulation = circadian_clock.simulate_clock(hours=72)
    assert 23.0 <= simulation["period_hours"] <= 25.5
    assert np.ptp(simulation["genes"]["CCA1"][-400:]) > 0.8


def test_clock_phase_order_matches_dawn_to_evening_progression():
    simulation = circadian_clock.simulate_clock(hours=48)
    phases = [
        circadian_clock.peak_phase_hours(simulation, symbol)
        for symbol in ("CCA1", "PRR9", "PRR7", "PRR5", "TOC1", "LUX")
    ]
    assert phases == sorted(phases)
    assert phases[-1] - phases[0] >= 14.0


def test_morning_module_overexpression_collapses_evening_rhythm():
    wild_type = circadian_clock.simulate_clock(hours=72)
    perturbed = circadian_clock.simulate_clock(hours=72, perturb_at=24.0)
    late = wild_type["time"] >= 48.0
    wt_amplitude = np.ptp(wild_type["genes"]["LUX"][late])
    ox_amplitude = np.ptp(perturbed["genes"]["LUX"][late])
    assert ox_amplitude < 0.2 * wt_amplitude


def test_clock_evidence_comes_from_atlas_signed_edges():
    genes = circadian_clock.resolve_clock_genes(main.db)
    edges = circadian_clock.load_atlas_clock_edges(main.db)
    assert len(genes) == 12
    assert len(edges) >= 19
    assert all(edge["sign_evidence"] in {"measured", "perturbation"} for edge in edges)
    assert all(edge["source_id"] != edge["target_id"] for edge in edges)
