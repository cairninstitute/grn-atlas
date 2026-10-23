from clonelab.interpretation import interpret_bands


def test_interpretation_selects_only_compatible_hypothesis():
    result = interpret_bands(
        [795, 205],
        {"intended": [800, 200], "reverse": [600, 400], "empty": [1000]},
    )
    assert result["compatible_hypotheses"] == ["intended"]
    assert result["ambiguous"] is False


def test_interpretation_preserves_ambiguity():
    result = interpret_bands(
        [800, 200],
        {"a": [800, 200], "b": [810, 195]},
    )
    assert result["compatible_hypotheses"] == ["a", "b"]
    assert result["ambiguous"] is True


def test_interpretation_reports_missing_and_unexpected_bands():
    result = interpret_bands([800, 200, 75], {"intended": [800, 200]})
    assert result["rankings"][0]["unexpected_band_count"] == 1
    assert result["compatible_hypotheses"] == []
