import json
from pathlib import Path
from urllib.error import URLError

from local_ai_control_center_installer.control_center_backend.services.search_provider_service import (
    _write_bootstrap_script,
    bootstrap_search_provider,
    load_search_provider_state,
    load_search_provider_status,
)


class _FakeResponse:
    def __init__(self, body: str):
        self._body = body

    def read(self) -> bytes:
        return self._body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _write_settings(install_root: Path, payload: dict[str, object]) -> None:
    settings_path = install_root / "config" / "control-center" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_search_provider_status_reports_not_configured_when_base_url_is_blank(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "off",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "",
        },
    )

    status = load_search_provider_status(
        opener=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("network should not run")),
    )

    assert status["status"] == "not-configured"
    assert status["source"] == "none"
    assert "nije podesen" in str(status["summary"]).lower()
    assert status["canQuery"] is False


def test_search_provider_status_reports_wrong_service_for_html_response(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "on-demand",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
        },
    )

    status = load_search_provider_status(
        opener=lambda request, timeout: _FakeResponse(
            "<!doctype html><html><head><title>Open WebUI</title></head><body></body></html>"
        ),
    )

    assert status["status"] == "wrong-service"
    assert status["serviceLabel"] == "Open WebUI"
    assert "drugi servis" in str(status["summary"]).lower()
    assert status["canQuery"] is False


def test_search_provider_status_treats_unreachable_legacy_default_as_not_configured(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "off",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:8080",
        },
    )

    status = load_search_provider_status(
        opener=lambda request, timeout: (_ for _ in ()).throw(URLError("connection refused")),
    )

    assert status["status"] == "not-configured"
    assert status["source"] == "none"
    assert "nije podesen" in str(status["summary"]).lower()
    assert status["canQuery"] is False


def test_search_provider_status_reports_healthy_for_valid_json_response(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "always",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18083/search",
        },
    )

    status = load_search_provider_status(
        opener=lambda request, timeout: _FakeResponse(
            json.dumps({"query": "health", "results": [], "answers": []})
        ),
    )

    assert status["status"] == "healthy"
    assert status["source"] == "manual"
    assert status["effectiveBaseUrl"] == "http://127.0.0.1:18083/search"
    assert status["canQuery"] is True


def test_bootstrap_search_provider_reports_blocked_when_wsl_is_unavailable(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    payload = bootstrap_search_provider(
        command_runner=lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("wsl")),
    )

    assert payload["result"]["status"] == "error"
    assert payload["providerStatus"]["status"] == "bootstrap-blocked"
    assert "wsl" in str(payload["providerStatus"]["summary"]).lower()

    state = load_search_provider_state()
    assert state["managed"]["lastBootstrapStatus"] == "bootstrap-blocked"


def test_bootstrap_search_provider_sanitizes_null_padded_wsl_distro_name(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    class _Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _command_runner(args, **kwargs):
        if args[:3] == ["wsl", "-l", "-q"]:
            return _Completed(0, "U\x00b\x00u\x00n\x00t\x00u\x00\n")
        assert args[:2] == ["wsl", "-d"]
        assert args[2] == "Ubuntu"
        return _Completed(0, "bootstrap ok", "")

    payload = bootstrap_search_provider(
        command_runner=_command_runner,
        opener=lambda request, timeout: _FakeResponse(
            json.dumps({"query": "health", "results": [], "answers": []})
        ),
    )

    assert payload["result"]["status"] == "ok"
    assert payload["providerStatus"]["status"] == "healthy"

    state = load_search_provider_state()
    assert state["managed"]["distro"] == "Ubuntu"


def test_write_bootstrap_script_uses_unix_newlines():
    script_path = _write_bootstrap_script(
        {
            "repoPath": "$HOME/.local-ai-control-center/searxng/repo",
            "venvPath": "$HOME/.local-ai-control-center/searxng/.venv",
            "settingsPath": "$HOME/.local-ai-control-center/searxng/settings.yml",
            "logPath": "$HOME/.local-ai-control-center/searxng/searxng.log",
            "pidPath": "$HOME/.local-ai-control-center/searxng/searxng.pid",
            "port": 18083,
        }
    )

    content = script_path.read_bytes()
    assert b"\r\n" not in content
    assert b"$HOME/.local-ai-control-center/searxng/repo" in content
    assert b"export BASE_DIR REPO_DIR VENV_DIR SETTINGS_PATH LOG_PATH PID_PATH PORT" in content
