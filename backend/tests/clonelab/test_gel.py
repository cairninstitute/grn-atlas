import pytest

from clonelab.gel import migration_for_size, simulate_gel


def test_migration_is_monotonic_with_fragment_size():
    sizes = [10_000, 5_000, 2_000, 1_000, 500, 100]
    migrations = [migration_for_size(size) for size in sizes]
    assert migrations == sorted(migrations)


def test_gel_merges_close_bands_and_retains_sources():
    result = simulate_gel([
        {"lane_id": "sample", "fragment_lengths": [1000, 990, 300]},
    ], ladder=None, resolution_fraction=0.02)
    bands = result["lanes"][0]["bands"]
    assert bands[0]["source_fragments_bp"] == [1000, 990]
    assert bands[0]["merged"] is True
    assert bands[1]["representative_bp"] == 300
    assert result["simulation"] is True


def test_uncut_circular_lane_is_not_given_linear_migration():
    lane = simulate_gel([
        {"lane_id": "uncut", "fragment_lengths": [], "uncut_circular": True},
    ], ladder=None)["lanes"][0]
    assert lane["bands"] == []
    assert "Uncut circular DNA" in lane["warning"]


def test_unknown_ladder_fails_explicitly():
    with pytest.raises(ValueError, match="unknown ladder"):
        simulate_gel([{"lane_id": "x", "fragment_lengths": [100]}], ladder="unknown")
