import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.runtime_bootstrap import (
    _write_runtime_endpoint_config,
)


def _write_active_model_config(install_root: Path, *, filename: str) -> None:
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    model_path = install_root / "models" / "recommended-6gb" / filename
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    (config_root / "active-model.json").write_text(
        json.dumps(
            {
                "model_id": "recommended-6gb",
                "model_path": str(model_path),
            }
        ),
        encoding="utf-8",
    )


def _write_settings(install_root: Path, payload: dict[str, object]) -> None:
    settings_path = install_root / "config" / "control-center" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_turboquant_config(install_root: Path, payload: dict[str, object]) -> None:
    config_path = install_root / "config" / "control-center" / "turboquant-config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_server_status_route_reports_started_runtime_snapshot(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
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
        "local_ai_control_center_installer.control_center_backend.services.server_service.probe_server_health",
        lambda *args, **kwargs: "ready",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.find_runtime_pid",
        lambda *args, **kwargs: 5150,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.detect_tailscale_ip",
        lambda: "",
    )

    client = TestClient(app)
    response = client.get("/api/server/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "started"
    assert payload["lifecycleState"] == "started"
    assert payload["port"] == 39281
    assert payload["health"] == "ok"
    assert payload["pid"] == 5150
    assert payload["activeModel"] == "gemma-4-E4B-it-Q4_K_M.gguf"
    assert payload["activeRuntime"] == "llama.cpp"
    assert payload["activeRuntimeLabel"] == "llama.cpp"
    assert payload["runtimeLiveStatus"] == "started"
    assert payload["healthUrl"] == "http://127.0.0.1:39281/health"
    assert payload["webUrl"] == "http://127.0.0.1:39281/"
    assert payload["localWebUrl"] == "http://127.0.0.1:39281/"
    assert payload["tailscaleWebUrl"] == ""
    assert payload["hasWarning"] is False


def test_server_status_route_reports_warning_when_runtime_is_warming(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
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
        "local_ai_control_center_installer.control_center_backend.services.server_service.probe_server_health",
        lambda *args, **kwargs: "loading",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.find_runtime_pid",
        lambda *args, **kwargs: 5150,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.detect_tailscale_ip",
        lambda: "",
    )

    client = TestClient(app)
    response = client.get("/api/server/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "warming"
    assert payload["health"] == "loading"
    assert payload["hasWarning"] is True
    assert payload["warningSeverity"] == "warning"
    assert "loading" in payload["warningSummary"].lower()


def test_server_start_route_spawns_runtime_process(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    executable = runtime_root / "llama-server.exe"
    executable.write_text("llama", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 7001

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

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
        fake_popen,
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "Pokretanje runtime servera je poslato" in payload["summary"]
    command = captured["command"]
    assert command[0].endswith("llama-server.exe")
    assert "--port" in command
    assert "39281" in command
    assert "--model" in command
    assert any(str(item).endswith("gemma-4-E4B-it-Q4_K_M.gguf") for item in command)


def test_server_stop_route_reports_ok_when_runtime_is_already_stopped(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
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
        "local_ai_control_center_installer.control_center_backend.services.server_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )

    client = TestClient(app)
    response = client.post("/api/server/stop")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "Runtime server je već zaustavljen" in payload["summary"]


def test_server_stop_route_cleans_orphaned_runtime_process_without_listener(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
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
        "local_ai_control_center_installer.control_center_backend.services.server_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service._stop_orphaned_runtime_processes",
        lambda install_root: True,
    )

    client = TestClient(app)
    response = client.post("/api/server/stop")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "preostali runtime procesi" in payload["summary"]


def test_server_open_web_route_returns_local_runtime_url(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
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
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.run",
        lambda *args, **kwargs: type(
            "CompletedProcess",
            (),
            {"returncode": 0, "stdout": "", "stderr": ""},
        )(),
    )

    client = TestClient(app)
    response = client.post("/api/server/open-web")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "http://127.0.0.1:39281/" in payload["summary"]


def test_server_start_route_falls_back_to_llama_when_selected_turboquant_is_not_launchable(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    executable = runtime_root / "llama-server.exe"
    executable.write_text("llama", encoding="utf-8")
    turbo_root = install_root / "tools" / "turboquant" / "windows-x64-cuda12.4"
    turbo_root.mkdir(parents=True, exist_ok=True)
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

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 7002

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

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
        "local_ai_control_center_installer.control_center_backend.services.status_service.probe_runtime_binary_launchable",
        lambda path: (False, "TurboQuant launch probe failed.")
        if "turboquant" in str(path).lower()
        else (True, "llama.cpp launch probe passed."),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    command = captured["command"]
    assert command[0].endswith("runtime\\llama.cpp\\llama-server.exe")


def test_server_start_route_adds_draft_mtp_flag_for_supported_mtp_active_model(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    executable = runtime_root / "llama-server.exe"
    executable.write_text("llama", encoding="utf-8")
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    mtp_model_path = (
        install_root
        / "models"
        / "unsloth"
        / "unsloth-qwen3-6-27b-mtp-gguf"
        / "Qwen3.6-27B-UD-IQ2_XXS.gguf"
    )
    mtp_model_path.parent.mkdir(parents=True, exist_ok=True)
    mtp_model_path.write_text("mtp-model", encoding="utf-8")
    (config_root / "active-model.json").write_text(
        json.dumps(
            {
                "model_id": "unsloth-unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-iq2-xxs",
                "model_path": str(mtp_model_path),
            }
        ),
        encoding="utf-8",
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
        "local_ai_control_center_installer.control_center_backend.services.status_service.runtime_supports_draft_mtp",
        lambda path: True,
        raising=False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.runtime_supports_draft_mtp",
        lambda path: True,
        raising=False,
    )
    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 7003

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    command = captured["command"]
    assert "--spec-type" in command
    assert "draft-mtp" in command


def test_server_start_route_allows_hardware_risky_active_model_to_attempt_launch(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    executable = runtime_root / "llama-server.exe"
    executable.write_text("llama", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 7004

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

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
        "local_ai_control_center_installer.control_center_backend.services.server_service._evaluate_runtime_hardware_fit",
        lambda *args, **kwargs: (False, "Model nije realno upotrebljiv na ovoj mašini."),
        raising=False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "Pokretanje runtime servera je poslato" in payload["summary"]
    assert captured["command"][0].endswith("llama-server.exe")


def test_server_status_route_exposes_start_block_reason_for_unsupported_active_model(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    mtp_model_path = (
        install_root
        / "models"
        / "unsloth"
        / "unsloth-qwen3-6-27b-mtp-gguf"
        / "Qwen3.6-27B-UD-IQ2_XXS.gguf"
    )
    mtp_model_path.parent.mkdir(parents=True, exist_ok=True)
    mtp_model_path.write_text("mtp-model", encoding="utf-8")
    (config_root / "active-model.json").write_text(
        json.dumps(
            {
                "model_id": "unsloth-unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-iq2-xxs",
                "model_path": str(mtp_model_path),
            }
        ),
        encoding="utf-8",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.probe_server_health",
        lambda *args, **kwargs: "offline",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.detect_tailscale_ip",
        lambda: "",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.runtime_supports_draft_mtp",
        lambda path: False,
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/server/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["canStart"] is False
    assert "MTP" in payload["startBlockedReason"]
    assert payload["canOpenWeb"] is False


def test_status_route_falls_back_to_llama_for_mtp_model_when_turboquant_is_selected(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    llama_root = install_root / "runtime" / "llama.cpp"
    turbo_root = install_root / "tools" / "turboquant" / "windows-x64-cuda12.4"
    llama_root.mkdir(parents=True)
    turbo_root.mkdir(parents=True, exist_ok=True)
    (llama_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    (turbo_root / "llama-server.exe").write_text("turbo", encoding="utf-8")
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    mtp_model_path = (
        install_root
        / "models"
        / "unsloth"
        / "unsloth-qwen3-6-27b-mtp-gguf"
        / "Qwen3.6-27B-UD-IQ2_XXS.gguf"
    )
    mtp_model_path.parent.mkdir(parents=True, exist_ok=True)
    mtp_model_path.write_text("mtp-model", encoding="utf-8")
    (config_root / "active-model.json").write_text(
        json.dumps(
            {
                "model_id": "unsloth-unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-iq2-xxs",
                "model_path": str(mtp_model_path),
            }
        ),
        encoding="utf-8",
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
        "local_ai_control_center_installer.control_center_backend.services.server_service.probe_server_health",
        lambda *args, **kwargs: "offline",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.detect_tailscale_ip",
        lambda: "",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.runtime_supports_draft_mtp",
        lambda path: "runtime\\llama.cpp" in str(path).lower().replace("/", "\\"),
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/server/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["activeRuntimeLabel"] == "llama.cpp"
    assert payload["requestedRuntimeLabel"] == "TurboQuant"
    assert payload["canStart"] is True
    assert "MTP" in payload["warningSummary"] or "MTP" in payload["lastReason"] or "MTP" in payload["runtimeSelectionSummary"]


def test_server_status_route_exposes_open_web_block_while_runtime_is_stopped(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
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
        "local_ai_control_center_installer.control_center_backend.services.server_service.probe_server_health",
        lambda *args, **kwargs: "offline",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.detect_tailscale_ip",
        lambda: "",
    )

    client = TestClient(app)
    response = client.get("/api/server/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "stopped"
    assert payload["canOpenWeb"] is False
    assert "nije spreman" in payload["openWebBlockedReason"].lower()


def test_server_start_route_restarts_unhealthy_managed_runtime_listener(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    executable = runtime_root / "llama-server.exe"
    executable.write_text("llama", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 7010

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.find_runtime_pid",
        lambda *args, **kwargs: 5150,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.find_runtime_pid",
        lambda *args, **kwargs: 5150,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.probe_server_health",
        lambda *args, **kwargs: "offline",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.is_managed_runtime_port_owned_by_installation",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.stop_managed_runtime_on_port",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "restart" in payload["summary"].lower()
    command = captured["command"]
    assert command[0].endswith("llama-server.exe")
    assert "39281" in command


def test_server_start_route_uses_saved_global_context_for_llama_runtime(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    executable = runtime_root / "llama-server.exe"
    executable.write_text("llama", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    _write_settings(
        install_root,
        {
            "profile": "balanced",
            "context": 65536,
            "outputTokens": 8192,
            "workingDirectory": str(install_root),
            "thinkingMode": "mid",
            "buildSteps": 140,
            "planSteps": 100,
            "generalSteps": 110,
            "exploreSteps": 80,
            "accessMode": "local-only",
            "securityMode": "strict",
            "capabilityMode": "confirm-commands",
        },
    )

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 7003

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

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
        "local_ai_control_center_installer.control_center_backend.services.status_service.probe_runtime_binary_launchable",
        lambda path: (True, "launch probe passed."),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    command = captured["command"]
    assert "--ctx-size" in command
    assert command[command.index("--ctx-size") + 1] == "65536"


def test_server_start_route_uses_saved_turboquant_context_for_turboquant_runtime(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    turbo_root = install_root / "tools" / "turboquant" / "windows-x64-cuda12.4"
    turbo_root.mkdir(parents=True, exist_ok=True)
    (turbo_root / "llama-server.exe").write_text("turbo", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    _write_settings(
        install_root,
        {
            "profile": "balanced",
            "context": 262144,
            "outputTokens": 8192,
            "workingDirectory": str(install_root),
            "thinkingMode": "mid",
            "buildSteps": 140,
            "planSteps": 100,
            "generalSteps": 110,
            "exploreSteps": 80,
            "accessMode": "local-only",
            "securityMode": "strict",
            "capabilityMode": "confirm-commands",
        },
    )
    _write_turboquant_config(
        install_root,
        {
            "context": 131072,
            "ctk": "turbo4",
            "ctv": "turbo3",
            "ncmoe": 20,
            "flashAttention": True,
            "mlock": True,
            "mmapMode": "mmap",
            "runtimePreference": "turboquant",
        },
    )
    selection_path = install_root / "config" / "control-center" / "runtime-selection.json"
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(json.dumps({"runtime": "turboquant"}), encoding="utf-8")

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 7004

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

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
        "local_ai_control_center_installer.control_center_backend.services.status_service.probe_runtime_binary_launchable",
        lambda path: (True, "launch probe passed."),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    command = captured["command"]
    assert command[0].endswith("tools\\turboquant\\windows-x64-cuda12.4\\llama-server.exe")
    assert "--ctx-size" in command
    assert command[command.index("--ctx-size") + 1] == "131072"


def test_server_start_route_uses_safe_default_turboquant_context_when_config_is_missing(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    turbo_root = install_root / "tools" / "turboquant" / "windows-x64-cuda12.4"
    turbo_root.mkdir(parents=True, exist_ok=True)
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

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 7005

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

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
        "local_ai_control_center_installer.control_center_backend.services.status_service.probe_runtime_binary_launchable",
        lambda path: (True, "launch probe passed."),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    command = captured["command"]
    assert command[0].endswith("tools\\turboquant\\windows-x64-cuda12.4\\llama-server.exe")
    assert "--ctx-size" in command
    assert command[command.index("--ctx-size") + 1] == "131072"
