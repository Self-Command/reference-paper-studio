import pytest
from studio.runtime import StudioError, confined, require_actions


def test_cloud_only_boundary(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(StudioError, match="CLOUD_ONLY"):
        require_actions()


def test_input_path_boundary(tmp_path):
    with pytest.raises(StudioError, match="PATH_ESCAPE"):
        confined(tmp_path, "../outside.md")
