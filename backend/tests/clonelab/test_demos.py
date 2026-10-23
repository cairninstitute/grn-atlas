from clonelab.demos import list_demonstrations


def test_release_demonstrations_are_declared_and_evidence_bounded():
    demos = {row["demonstration_id"]: row for row in list_demonstrations()}
    assert set(demos) == {"arabidopsis_clock", "petunia_pigmentation"}
    assert demos["arabidopsis_clock"]["gene_id"] == "AT2G46830"
    assert demos["petunia_pigmentation"]["gene_symbol"] == "AN2"
    assert all("not a plant expression vector" in row["boundary"] for row in demos.values())
