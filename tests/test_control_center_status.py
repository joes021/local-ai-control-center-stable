import importlib
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.control_center_backend.config import get_config
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


def test_status_route_falls_back_to_windows_display_version_when_package_metadata_is_unavailable(
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
        "local_ai_control_center_installer.control_center_backend.services.status_service._read_running_version_from_source_tree",
        lambda: None,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.package_version",
        lambda _: (_ for _ in ()).throw(status_service.PackageNotFoundError()),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service._query_windows_display_version",
        lambda: "0.4.1",
    )
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
    assert payload["version"] == "0.4.1"
    assert payload["installedVersion"] == "0.4.1"


def test_status_route_prefers_running_source_version_over_installed_report_version(
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
    logs_root = install_root / "logs"
    logs_root.mkdir(parents=True, exist_ok=True)
    (logs_root / "install-report.json").write_text(
        json.dumps({"product_version": "0.4.90"}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service._read_running_version_from_source_tree",
        lambda: "0.4.94",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.package_version",
        lambda _: "0.4.90",
    )
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
    assert payload["version"] == "0.4.94"
    assert payload["installedVersion"] == "0.4.90"


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


def test_status_route_reports_degraded_when_listener_exists_without_health(
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
        lambda *args, **kwargs: 4242,
    )

    client = TestClient(app)
    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtimeLiveStatus"] == "degraded"
    assert "health" in payload["runtimeLiveReason"].lower()


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
    assert payload["requestedRuntimeLabel"] == "TurboQuant"
    assert "TurboQuant" in payload["runtimeSelectionSummary"]
    assert "llama.cpp" in payload["runtimeSelectionSummary"]
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


def test_runtime_supports_draft_mtp_returns_true_when_help_advertises_capability(
    tmp_path: Path,
    monkeypatch,
):
    binary_path = tmp_path / "runtime" / "llama.cpp" / "llama-server.exe"
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_text("binary", encoding="utf-8")
    status_service._runtime_supports_draft_mtp_cached.cache_clear()

    monkeypatch.setattr(
        status_service,
        "detect_missing_sidecar_imports",
        lambda path: (),
        raising=False,
    )

    def _fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout="--spec-type [none|draft-mtp]\n",
            stderr="",
        )

    monkeypatch.setattr(status_service.subprocess, "run", _fake_run)

    assert status_service.runtime_supports_draft_mtp(binary_path) is True


def test_runtime_supports_draft_mtp_returns_false_without_advertised_capability(
    tmp_path: Path,
    monkeypatch,
):
    binary_path = tmp_path / "tools" / "turboquant" / "llama-server.exe"
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_text("binary", encoding="utf-8")
    status_service._runtime_supports_draft_mtp_cached.cache_clear()

    monkeypatch.setattr(
        status_service,
        "detect_missing_sidecar_imports",
        lambda path: (),
        raising=False,
    )

    def _fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout="--spec-type [none|ngram-cache|ngram-simple]\n",
            stderr="",
        )

    monkeypatch.setattr(status_service.subprocess, "run", _fake_run)

    assert status_service.runtime_supports_draft_mtp(binary_path) is False


def test_load_runtime_state_reuses_recent_snapshot(monkeypatch, tmp_path: Path):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_active_model_config(install_root, filename="demo.gguf")
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    llama_binary = install_root / "runtime" / "llama.cpp" / "llama-server.exe"
    turbo_binary = install_root / "tools" / "turboquant" / "windows-x64-cuda12.4" / "llama-server.exe"
    llama_binary.parent.mkdir(parents=True, exist_ok=True)
    turbo_binary.parent.mkdir(parents=True, exist_ok=True)
    llama_binary.write_text("llama", encoding="utf-8")
    turbo_binary.write_text("turbo", encoding="utf-8")

    module = importlib.reload(status_service)
    config = get_config()
    calls = {
        "probe_binary": 0,
        "resolve_runtime": 0,
        "classify": 0,
        "health": 0,
        "pid": 0,
        "profile": 0,
    }

    monkeypatch.setattr(
        module,
        "load_runtime_manifest",
        lambda: {"runtime_artifact": {"install_subdir": "runtime/llama.cpp"}},
    )
    monkeypatch.setattr(
        module,
        "load_turboquant_manifest",
        lambda: {
            "turboquant_artifact": {
                "install_subdir": "tools/turboquant/windows-x64-cuda12.4",
                "launch": {"executable_relative_path": "llama-server.exe"},
            }
        },
    )
    monkeypatch.setattr(
        module,
        "probe_runtime_binary_launchable",
        lambda path: (
            calls.__setitem__("probe_binary", calls["probe_binary"] + 1) or True,
            f"{Path(path).name} ready",
        ),
    )
    monkeypatch.setattr(
        module,
        "_resolve_selected_runtime",
        lambda *args, **kwargs: (
            calls.__setitem__("resolve_runtime", calls["resolve_runtime"] + 1) or {
                "requested_runtime": "llama.cpp",
                "selection_source": "selection",
                "active_runtime": "llama.cpp",
                "selection_summary": "Koristi se izabrani runtime: llama.cpp.",
            }
        ),
    )
    monkeypatch.setattr(
        module,
        "classify_runtime_model_support",
        lambda **kwargs: (
            calls.__setitem__("classify", calls["classify"] + 1) or True,
            "",
        ),
    )
    monkeypatch.setattr(
        module,
        "probe_server_health",
        lambda base_url: calls.__setitem__("health", calls["health"] + 1) or "ready",
    )
    monkeypatch.setattr(
        module,
        "find_runtime_pid",
        lambda port: calls.__setitem__("pid", calls["pid"] + 1) or 4242,
    )
    monkeypatch.setattr(
        module,
        "_load_profile",
        lambda config: calls.__setitem__("profile", calls["profile"] + 1) or "balanced",
    )

    first = module.load_runtime_state(config)
    second = module.load_runtime_state(config)

    assert first["active_runtime"] == "llama.cpp"
    assert second["runtime_live_status"] == "started"
    assert calls == {
        "probe_binary": 2,
        "resolve_runtime": 1,
        "classify": 1,
        "health": 1,
        "pid": 1,
        "profile": 1,
    }


def test_load_runtime_state_deduplicates_parallel_cold_requests(monkeypatch, tmp_path: Path):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_active_model_config(install_root, filename="demo.gguf")
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    llama_binary = install_root / "runtime" / "llama.cpp" / "llama-server.exe"
    turbo_binary = install_root / "tools" / "turboquant" / "windows-x64-cuda12.4" / "llama-server.exe"
    llama_binary.parent.mkdir(parents=True, exist_ok=True)
    turbo_binary.parent.mkdir(parents=True, exist_ok=True)
    llama_binary.write_text("llama", encoding="utf-8")
    turbo_binary.write_text("turbo", encoding="utf-8")

    module = importlib.reload(status_service)
    config = get_config()
    calls = {
        "probe_binary": 0,
        "resolve_runtime": 0,
        "classify": 0,
        "health": 0,
        "pid": 0,
        "profile": 0,
    }
    first_call_entered = threading.Event()
    release_first_call = threading.Event()
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []

    monkeypatch.setattr(
        module,
        "load_runtime_manifest",
        lambda: {"runtime_artifact": {"install_subdir": "runtime/llama.cpp"}},
    )
    monkeypatch.setattr(
        module,
        "load_turboquant_manifest",
        lambda: {
            "turboquant_artifact": {
                "install_subdir": "tools/turboquant/windows-x64-cuda12.4",
                "launch": {"executable_relative_path": "llama-server.exe"},
            }
        },
    )
    monkeypatch.setattr(
        module,
        "probe_runtime_binary_launchable",
        lambda path: (
            calls.__setitem__("probe_binary", calls["probe_binary"] + 1) or True,
            f"{Path(path).name} ready",
        ),
    )
    monkeypatch.setattr(
        module,
        "_resolve_selected_runtime",
        lambda *args, **kwargs: (
            calls.__setitem__("resolve_runtime", calls["resolve_runtime"] + 1) or {
                "requested_runtime": "llama.cpp",
                "selection_source": "selection",
                "active_runtime": "llama.cpp",
                "selection_summary": "Koristi se izabrani runtime: llama.cpp.",
            }
        ),
    )
    monkeypatch.setattr(
        module,
        "classify_runtime_model_support",
        lambda **kwargs: (
            calls.__setitem__("classify", calls["classify"] + 1) or True,
            "",
        ),
    )

    def fake_health(base_url: str) -> str:
        calls["health"] += 1
        if calls["health"] == 1:
            first_call_entered.set()
            assert release_first_call.wait(timeout=5)
        return "ready"

    monkeypatch.setattr(module, "probe_server_health", fake_health)
    monkeypatch.setattr(
        module,
        "find_runtime_pid",
        lambda port: calls.__setitem__("pid", calls["pid"] + 1) or 4242,
    )
    monkeypatch.setattr(
        module,
        "_load_profile",
        lambda config: calls.__setitem__("profile", calls["profile"] + 1) or "balanced",
    )

    def worker() -> None:
        try:
            results.append(module.load_runtime_state(config))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    first_thread = threading.Thread(target=worker, daemon=True)
    second_thread = threading.Thread(target=worker, daemon=True)
    first_thread.start()
    assert first_call_entered.wait(timeout=5)
    second_thread.start()
    time.sleep(0.1)
    release_first_call.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert errors == []
    assert len(results) == 2
    assert all(result["runtime_live_status"] == "started" for result in results)
    assert calls == {
        "probe_binary": 2,
        "resolve_runtime": 1,
        "classify": 1,
        "health": 1,
        "pid": 1,
        "profile": 1,
    }


def test_find_runtime_pid_reuses_recent_probe(monkeypatch):
    module = importlib.reload(status_service)
    calls: list[dict[str, object]] = []

    class FakeCompletedProcess:
        returncode = 0
        stdout = (
            "Proto  Local Address          Foreign Address        State           PID\r\n"
            "TCP    127.0.0.1:3210         0.0.0.0:0              LISTENING       4242\r\n"
        )
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return FakeCompletedProcess()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    first = module.find_runtime_pid(3210)
    second = module.find_runtime_pid(3210)

    assert first == 4242
    assert second == first
    assert len(calls) == 1
    assert calls[0]["creationflags"] == getattr(module.subprocess, "CREATE_NO_WINDOW", 0)
