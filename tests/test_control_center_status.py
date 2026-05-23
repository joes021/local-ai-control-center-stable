import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.control_center_backend.services import (
    status_service,
)
from local_ai_control_center_installer.runtime_bootstrap import (
    _write_runtime_endpoint_config,
)


def _write_active_model_config(install_root: Path, *, filename: str) -> Path:
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    model_path = install_root / "models" / "recommended-6gb" / filename
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    path = config_root / "active-model.json"
    path.write_text(
        json.dumps(
            {
                "model_id": "recommended-6gb",
                "model_path": str(model_path),
            }
        ),
        encoding="utf-8",
    )
    return path


def test_status_route_returns_installer_managed_runtime_snapshot(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    llama_root = install_root / "runtime" / "llama.cpp"
    turbo_root = install_root / "tools" / "turboquant" / "windows-x64-cuda12.4"
    llama_root.mkdir(parents=True)
    turbo_root.mkdir(parents=True)
    (llama_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    (turbo_root / "llama-server.exe").write_text("turbo", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.probe_server_health",
        lambda *args, **kwargs: "ready",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.detect_tailscale_ip",
        lambda: "",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.find_runtime_pid",
        lambda *args, **kwargs: 4242,
    )

    client = TestClient(app)
    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["health"] == "ok"
    assert payload["activeModel"] == "gemma-4-E4B-it-Q4_K_M.gguf"
    assert payload["uiPort"] == 3210
    assert payload["uiUrl"] == "http://127.0.0.1:3210/"
    assert payload["localUrl"] == "http://127.0.0.1:3210/"
    assert payload["tailscaleUrl"] == ""
    assert payload["activeRuntimeLabel"] == "llama.cpp"
    assert payload["availableRuntimes"] == ["llama.cpp", "TurboQuant"]
    assert payload["llamaRuntimeAvailable"] is True
    assert payload["turboQuantRuntimeAvailable"] is True
    assert payload["llamaCppStatus"] == "ready"
    assert payload["turboQuantStatus"] == "ready"
    assert payload["turboQuantDisplayState"] == "available"
    assert payload["turboQuantSummary"] == "TurboQuant je dostupan za aktivaciju."
    assert "aktivirati" in payload["turboQuantGuidance"]
    assert payload["runtimeLiveStatus"] == "started"
    assert "Runtime health endpoint" in payload["runtimeLiveReason"]
    assert payload["activeRuntimeBinary"].endswith("runtime\\llama.cpp\\llama-server.exe")


def test_status_route_reports_ui_not_exposed_when_tailscale_is_missing(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    llama_root = install_root / "runtime" / "llama.cpp"
    llama_root.mkdir(parents=True)
    (llama_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.probe_server_health",
        lambda *args, **kwargs: "offline",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.detect_tailscale_ip",
        lambda: "",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )

    client = TestClient(app)
    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtimeLiveStatus"] == "stopped"
    assert payload["tailscaleUrl"] == ""
    assert payload["runtimeSummary"].startswith("Aktivan runtime:")


def test_status_route_falls_back_to_llama_when_selected_turboquant_is_not_launchable(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    llama_root = install_root / "runtime" / "llama.cpp"
    turbo_root = install_root / "tools" / "turboquant" / "windows-x64-cuda12.4"
    llama_root.mkdir(parents=True)
    turbo_root.mkdir(parents=True)
    (llama_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    (turbo_root / "llama-server.exe").write_text("turbo", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    selection_path = install_root / "config" / "control-center" / "runtime-selection.json"
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(json.dumps({"runtime": "turboquant"}), encoding="utf-8")

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.probe_server_health",
        lambda *args, **kwargs: "ready",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.detect_tailscale_ip",
        lambda: "",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.find_runtime_pid",
        lambda *args, **kwargs: 4242,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.probe_runtime_binary_launchable",
        lambda path: (False, "TurboQuant launch probe failed.")
        if "turboquant" in str(path).lower()
        else (True, "llama.cpp launch probe passed."),
    )

    client = TestClient(app)
    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["activeRuntimeLabel"] == "llama.cpp"
    assert payload["activeRuntimeBinary"].endswith("runtime\\llama.cpp\\llama-server.exe")
    assert payload["activeRuntimeBinarySource"] == "fallback"
    assert payload["turboQuantRuntimeAvailable"] is False
    assert payload["turboQuantStatus"] == "failed"
    assert payload["turboQuantDisplayState"] == "disabled"
    assert payload["turboQuantSummary"] == "TurboQuant trenutno nije dostupan na ovoj instalaciji."
    assert "llama.cpp" in payload["turboQuantGuidance"]
    assert "launch probe failed" in payload["turboQuantReason"]


def test_probe_runtime_binary_launchable_reports_missing_sidecar_dlls_without_spawn(
    tmp_path: Path,
    monkeypatch,
):
    binary_path = (
        tmp_path
        / "tools"
        / "turboquant"
        / "windows-x64-cuda12.4"
        / "llama-server.exe"
    )
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_text("binary", encoding="utf-8")

    monkeypatch.delenv("LACC_SKIP_RUNTIME_LAUNCH_PROBE", raising=False)
    monkeypatch.setattr(
        status_service,
        "detect_missing_sidecar_imports",
        lambda path: ("libssl-3-x64.dll", "libcrypto-3-x64.dll"),
        raising=False,
    )

    def _unexpected_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called for missing DLL sidecars")

    monkeypatch.setattr(status_service.subprocess, "run", _unexpected_run)

    launchable, reason = status_service.probe_runtime_binary_launchable(binary_path)

    assert launchable is False
    assert "libssl-3-x64.dll" in reason
    assert "libcrypto-3-x64.dll" in reason
