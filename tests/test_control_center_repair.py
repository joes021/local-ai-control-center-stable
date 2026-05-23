import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.runtime_bootstrap import (
    _write_runtime_endpoint_config,
)


def _write_active_model_config(install_root: Path, *, model_id: str, model_path: Path) -> None:
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    (config_root / "active-model.json").write_text(
        json.dumps({"model_id": model_id, "model_path": str(model_path)}),
        encoding="utf-8",
    )


def test_logs_route_returns_install_root_logs_preview(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    logs_root = install_root / "logs"
    logs_root.mkdir(parents=True, exist_ok=True)
    (logs_root / "install.log").write_text("line-1\nline-2\n", encoding="utf-8")
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)
    response = client.get("/api/logs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "install.log" in payload["details"]["stdout"]
    assert "line-2" in payload["details"]["stdout"]


def test_runtime_repair_route_starts_runtime_when_server_is_not_running(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    _write_active_model_config(
        install_root,
        model_id="recommended-6gb",
        model_path=install_root / "models" / "recommended-6gb" / "gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        lambda *args, **kwargs: type("FakeProcess", (), {"pid": 7788})(),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.detect_tailscale_ip",
        lambda: "",
    )

    client = TestClient(app)
    response = client.post("/api/repair/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["repairKind"] == "runtime"
    assert "Runtime je dobio novi start zahtev" in payload["userMessage"]
