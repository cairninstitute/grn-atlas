import pytest

from clonelab.external_validation import ExternalToolUnavailable, find_emboss_restrict


def test_missing_external_tool_fails_explicitly(tmp_path, monkeypatch):
    monkeypatch.setattr("clonelab.external_validation.shutil.which", lambda _name: None)
    monkeypatch.delenv("EMBOSS_RESTRICT", raising=False)
    with pytest.raises(ExternalToolUnavailable, match="EMBOSS restrict"):
        find_emboss_restrict(tmp_path / "missing")
