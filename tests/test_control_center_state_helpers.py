import json
from pathlib import Path


def test_atomic_write_json_retries_replace_on_windows_access_denied(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import state_helpers

    target_path = tmp_path / "state.json"
    attempts = {"count": 0}
    original_replace = Path.replace

    def flaky_replace(self: Path, target: Path):
        if self.parent == tmp_path and target == target_path and attempts["count"] == 0:
            attempts["count"] += 1
            error = PermissionError("Access denied")
            error.winerror = 5
            raise error
        return original_replace(self, target)

    monkeypatch.setattr(state_helpers.Path, "replace", flaky_replace)

    state_helpers.atomic_write_json(target_path, {"status": "ok"})

    assert attempts["count"] == 1
    assert json.loads(target_path.read_text(encoding="utf-8")) == {"status": "ok"}
