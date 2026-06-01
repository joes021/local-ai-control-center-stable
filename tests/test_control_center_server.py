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


def _write_runtime_log(install_root: Path, text: str) -> None:
    log_path = install_root / "logs" / "runtime-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(text, encoding="utf-8")


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
    assert payload["commandPreview"]["shellLabel"] == "PowerShell / cmd.exe"
    assert "--model" in payload["commandPreview"]["activeCommand"]
    assert "gemma-4-E4B-it-Q4_K_M.gguf" in payload["commandPreview"]["activeCommand"]
    assert "--temp 0.8" in payload["commandPreview"]["activeCommand"]
    assert "--top-k 40" in payload["commandPreview"]["activeCommand"]
    assert "--top-p 0.95" in payload["commandPreview"]["activeCommand"]
    assert payload["commandPreview"]["activeCmdCommand"].startswith('"')
    assert payload["commandPreview"]["modelPath"].endswith("gemma-4-E4B-it-Q4_K_M.gguf")
    assert any("Lokalni model" in note for note in payload["commandPreview"]["notes"])


def test_server_status_route_reports_context_mismatch_between_config_and_live_process(
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
        filename="Qwen3.6-28B-REAP20-A3B-Q4_K_M.gguf",
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
            "context": 16384,
            "ctk": "turbo2",
            "ctv": "turbo2",
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
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service._read_runtime_process_context_size",
        lambda pid: 19456,
    )

    client = TestClient(app)
    response = client.get("/api/server/status")

    assert response.status_code == 200
    payload = response.json()
    diagnostics = payload["runtimeDiagnostics"]
    assert diagnostics["configuredContext"] == 16384
    assert diagnostics["effectiveProcessContext"] == 19456
    assert diagnostics["contextMismatch"] is True
    assert diagnostics["contextAlignmentLabel"] == "Potreban restart runtime-a"
    assert "16384" in diagnostics["contextAlignmentSummary"]
    assert "19456" in diagnostics["contextAlignmentSummary"]


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
    from local_ai_control_center_installer.control_center_backend.services import server_service

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
    monkeypatch.setattr(server_service, "_runtime_binary_supports_flag", lambda *args, **kwargs: True)
    monkeypatch.setattr(server_service, "_detect_nvidia_total_memory_mib", lambda: 12 * 1024)
    monkeypatch.setattr(
        server_service,
        "_detect_nvidia_gpu_inventory",
        lambda: [
            {
                "index": 0,
                "name": "RTX 3060",
                "totalMemoryMiB": 12 * 1024,
                "usedMemoryMiB": 256,
            }
        ],
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
    assert "--temp" in command
    assert "0.8" in command
    assert "--top-k" in command
    assert "--top-p" in command
    assert "--repeat-last-n" in command
    assert "--seed" in command
    assert "--n-gpu-layers" in command
    assert command[command.index("--n-gpu-layers") + 1] == "40"
    assert "--flash-attn" in command
    assert command[command.index("--flash-attn") + 1] == "auto"
    assert any(str(item).endswith("gemma-4-E4B-it-Q4_K_M.gguf") for item in command)


def test_server_start_route_prefers_highest_vram_gpu_and_explicit_gpu_flags(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import server_service

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
    monkeypatch.setattr(server_service, "_runtime_binary_supports_flag", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        server_service,
        "_detect_nvidia_gpu_inventory",
        lambda: [
            {
                "index": 0,
                "name": "RTX 2060",
                "totalMemoryMiB": 6144,
                "usedMemoryMiB": 256,
            },
            {
                "index": 1,
                "name": "RTX 4090",
                "totalMemoryMiB": 24576,
                "usedMemoryMiB": 512,
            },
        ],
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    command = captured["command"]
    assert "--n-gpu-layers" in command
    assert command[command.index("--n-gpu-layers") + 1] == "99"
    assert "--main-gpu" in command
    assert command[command.index("--main-gpu") + 1] == "1"
    assert "--split-mode" in command
    assert command[command.index("--split-mode") + 1] == "none"


def test_server_start_route_respects_manual_gpu_layers_override(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import server_service

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
            "gpuLayersMode": "manual",
            "gpuLayersOverride": 41,
        },
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
    monkeypatch.setattr(server_service, "_runtime_binary_supports_flag", lambda *args, **kwargs: True)
    monkeypatch.setattr(server_service, "_detect_nvidia_total_memory_mib", lambda: 12 * 1024)
    monkeypatch.setattr(
        server_service,
        "_detect_nvidia_gpu_inventory",
        lambda: [
            {
                "index": 0,
                "name": "RTX 3060",
                "totalMemoryMiB": 12 * 1024,
                "usedMemoryMiB": 256,
            }
        ],
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    command = captured["command"]
    assert "--n-gpu-layers" in command
    assert command[command.index("--n-gpu-layers") + 1] == "41"


def test_server_start_route_retries_without_explicit_main_gpu_when_runtime_rejects_it(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import server_service

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

    launch_commands: list[list[str]] = []

    class FakeProcess:
        def __init__(self, pid: int, *, exit_immediately: bool) -> None:
            self.pid = pid
            self._exit_immediately = exit_immediately

        def poll(self):
            return 1 if self._exit_immediately else None

    def fake_popen(command, **kwargs):
        launch_commands.append(command)
        stdout_handle = kwargs.get("stdout")
        if hasattr(stdout_handle, "write"):
            if len(launch_commands) == 1:
                stdout_handle.write(
                    "E llama_prepare_model_devices: invalid value for main_gpu: 0 (available devices: 0)\n"
                )
                stdout_handle.write("E srv llama_server: exiting due to model loading error\n")
                stdout_handle.flush()
                return FakeProcess(7101, exit_immediately=True)
            stdout_handle.write("I srv init: using 23 threads for HTTP server\n")
            stdout_handle.flush()
        return FakeProcess(7102, exit_immediately=False)

    health_states = ["offline", "offline", "offline", "loading"]

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
        "local_ai_control_center_installer.control_center_backend.services.server_service.probe_server_health",
        lambda *args, **kwargs: health_states.pop(0) if health_states else "loading",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(server_service, "_runtime_binary_supports_flag", lambda *args, **kwargs: True)
    monkeypatch.setattr(server_service, "_detect_nvidia_total_memory_mib", lambda: 12 * 1024)
    monkeypatch.setattr(
        server_service,
        "_detect_nvidia_gpu_inventory",
        lambda: [
            {
                "index": 0,
                "name": "RTX 3060",
                "totalMemoryMiB": 12 * 1024,
                "usedMemoryMiB": 256,
            }
        ],
    )
    monkeypatch.setattr(server_service.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server_service, "_START_SERVER_READY_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(server_service, "_START_SERVER_READY_POLL_INTERVAL_SECONDS", 0.0)

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert len(launch_commands) == 2
    assert "--main-gpu" in launch_commands[0]
    assert "--split-mode" in launch_commands[0]
    assert "--main-gpu" not in launch_commands[1]
    assert "--split-mode" not in launch_commands[1]
    assert "bez `--main-gpu`" in payload["summary"]


def test_server_start_route_waits_for_log_flush_before_main_gpu_fallback(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import server_service

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

    launch_commands: list[list[str]] = []

    class FakeProcess:
        def __init__(self, pid: int, *, exit_immediately: bool) -> None:
            self.pid = pid
            self._exit_immediately = exit_immediately

        def poll(self):
            return 1 if self._exit_immediately else None

    def fake_popen(command, **kwargs):
        launch_commands.append(command)
        return FakeProcess(7200 + len(launch_commands), exit_immediately=len(launch_commands) == 1)

    health_states = ["offline", "offline", "offline", "loading"]
    log_reads = iter(
        [
            "",
            "E llama_prepare_model_devices: invalid value for main_gpu: 0 (available devices: 0)",
        ]
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
        "local_ai_control_center_installer.control_center_backend.services.server_service.probe_server_health",
        lambda *args, **kwargs: health_states.pop(0) if health_states else "loading",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(server_service, "_runtime_binary_supports_flag", lambda *args, **kwargs: True)
    monkeypatch.setattr(server_service, "_detect_nvidia_total_memory_mib", lambda: 12 * 1024)
    monkeypatch.setattr(
        server_service,
        "_detect_nvidia_gpu_inventory",
        lambda: [
            {
                "index": 0,
                "name": "RTX 3060",
                "totalMemoryMiB": 12 * 1024,
                "usedMemoryMiB": 256,
            }
        ],
    )
    monkeypatch.setattr(server_service.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server_service, "_START_SERVER_READY_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(server_service, "_START_SERVER_READY_POLL_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(
        server_service,
        "_read_runtime_log_excerpt",
        lambda *args, **kwargs: next(log_reads, "E llama_prepare_model_devices: invalid value for main_gpu: 0 (available devices: 0)"),
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert len(launch_commands) == 2
    assert "--main-gpu" in launch_commands[0]
    assert "--main-gpu" not in launch_commands[1]
    assert "bez `--main-gpu`" in payload["summary"]


def test_server_start_route_does_not_trust_loading_health_when_process_exits_right_after(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import server_service

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

    launch_commands: list[list[str]] = []

    class FakeProcess:
        def __init__(self, pid: int, poll_states: list[int | None]) -> None:
            self.pid = pid
            self._poll_states = list(poll_states)

        def poll(self):
            if self._poll_states:
                return self._poll_states.pop(0)
            return self._poll_states[-1] if self._poll_states else None

    def fake_popen(command, **kwargs):
        launch_commands.append(command)
        if len(launch_commands) == 1:
            return FakeProcess(7301, [None, 1, 1])
        return FakeProcess(7302, [None, None, None])

    health_states = ["offline", "loading", "offline", "loading", "loading", "loading"]

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
        "local_ai_control_center_installer.control_center_backend.services.server_service.probe_server_health",
        lambda *args, **kwargs: health_states.pop(0) if health_states else "loading",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(server_service, "_runtime_binary_supports_flag", lambda *args, **kwargs: True)
    monkeypatch.setattr(server_service, "_detect_nvidia_total_memory_mib", lambda: 12 * 1024)
    monkeypatch.setattr(
        server_service,
        "_detect_nvidia_gpu_inventory",
        lambda: [
            {
                "index": 0,
                "name": "RTX 3060",
                "totalMemoryMiB": 12 * 1024,
                "usedMemoryMiB": 256,
            }
        ],
    )
    monkeypatch.setattr(server_service.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(server_service, "_START_SERVER_READY_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(server_service, "_START_SERVER_READY_POLL_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(server_service, "_START_SERVER_EXIT_LOG_WAIT_SECONDS", 0.0)
    monkeypatch.setattr(
        server_service,
        "_read_runtime_log_excerpt",
        lambda *args, **kwargs: "E llama_prepare_model_devices: invalid value for main_gpu: 0 (available devices: 0)",
    )

    client = TestClient(app)
    response = client.post("/api/server/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert len(launch_commands) == 2
    assert "--main-gpu" in launch_commands[0]
    assert "--main-gpu" not in launch_commands[1]
    assert "bez `--main-gpu`" in payload["summary"]


def test_server_status_route_preview_shows_gpu_offload_flags_for_llama_runtime(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import server_service

    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service._runtime_binary_supports_flag",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service._detect_nvidia_total_memory_mib",
        lambda: 12 * 1024,
    )
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
    assert "--n-gpu-layers 40" in payload["commandPreview"]["activeCommand"]
    assert "--flash-attn auto" in payload["commandPreview"]["activeCommand"]
    assert any("GPU offload" in note for note in payload["commandPreview"]["notes"])


def test_server_status_route_reports_confirmed_gpu_offload_diagnostics(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import server_service

    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    _write_runtime_log(
        install_root,
        "\n".join(
            [
                "ggml_cuda_init: found 1 CUDA devices (Total VRAM: 12287 MiB):",
                "llama_params_fit_impl: projected to use 5548 MiB of device memory vs. 11245 MiB of free device memory",
                "common_params_fit_impl: projected to use 16154 MiB of host memory vs. 32535 MiB of total host memory",
                "llama_model_load_from_file_impl: using device CUDA0 (NVIDIA GeForce RTX 3060) (0000:01:00.0) - 11245 MiB free",
                "load_tensors: offloading output layer to GPU",
                "load_tensors: offloading 41 repeating layers to GPU",
                "load_tensors: offloaded 43/43 layers to GPU",
                "load_tensors:        CUDA0 model buffer size =  2883.51 MiB",
                "llama_kv_cache:      CUDA0 KV buffer size =  2048.00 MiB",
                "llama_kv_cache:      CUDA0 KV buffer size =   100.00 MiB",
                "sched_reserve:      CUDA0 compute buffer size =   517.00 MiB",
            ]
        ),
    )

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service._runtime_binary_supports_flag",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service._detect_nvidia_total_memory_mib",
        lambda: 12 * 1024,
    )
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
    diagnostics = payload["runtimeDiagnostics"]
    assert diagnostics["status"] == "confirmed"
    assert diagnostics["backend"] == "CUDA"
    assert diagnostics["deviceLabel"] == "NVIDIA GeForce RTX 3060"
    assert diagnostics["requestedGpuLayers"] == 40
    assert diagnostics["requestedFlashAttention"] == "auto"
    assert diagnostics["projectedDeviceMemoryMiB"] == 5548
    assert diagnostics["projectedHostMemoryMiB"] == 16154
    assert diagnostics["confirmedGpuLayers"] == 43
    assert diagnostics["confirmedTotalLayers"] == 43
    assert diagnostics["modelBufferMiB"] == 2883.51
    assert diagnostics["kvBufferMiB"] == 2148.0
    assert diagnostics["computeBufferMiB"] == 517.0
    assert "potvrđen" in diagnostics["summary"].lower()


def test_runtime_diagnostics_classify_gpu_vram_mode_with_explicit_gpu_selection(tmp_path: Path):
    from local_ai_control_center_installer.control_center_backend.services.server_service import load_runtime_diagnostics

    log_path = tmp_path / "runtime-server.log"
    log_path.write_text(
        "\n".join(
            [
                "ggml_cuda_init: found 1 CUDA devices (Total VRAM: 12287 MiB):",
                "llama_params_fit_impl: projected to use 5548 MiB of device memory vs. 11245 MiB of free device memory",
                "common_params_fit_impl: projected to use 16154 MiB of host memory vs. 32535 MiB of total host memory",
                "llama_model_load_from_file_impl: using device CUDA0 (NVIDIA GeForce RTX 3060) (0000:01:00.0) - 11245 MiB free",
                "load_tensors: offloading output layer to GPU",
                "load_tensors: offloading 41 repeating layers to GPU",
                "load_tensors: offloaded 43/43 layers to GPU",
                "CPU_Mapped model buffer size =  2208.00 MiB",
                "load_tensors:        CUDA0 model buffer size =  2883.51 MiB",
                "llama_kv_cache:      CUDA0 KV buffer size =  2048.00 MiB",
                "llama_kv_cache:      CUDA0 KV buffer size =   100.00 MiB",
                "sched_reserve:      CUDA0 compute buffer size =   517.00 MiB",
            ]
        ),
        encoding="utf-8",
    )

    diagnostics = load_runtime_diagnostics(
        runtime_name="llama.cpp",
        launch_arguments={
            "gpu_layers": 40,
            "flash_attn": "auto",
            "main_gpu": 0,
            "split_mode": "none",
        },
        log_path=log_path,
    )

    assert diagnostics["status"] == "confirmed"
    assert diagnostics["executionModeId"] == "gpu-vram"
    assert diagnostics["executionModeLabel"] == "GPU VRAM dominantno"
    assert diagnostics["requestedMainGpu"] == 0
    assert diagnostics["requestedSplitMode"] == "none"
    assert diagnostics["requestedSummary"]
    assert diagnostics["confirmedSummary"]


def test_server_status_route_uses_latest_kv_buffer_block_for_runtime_diagnostics(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
    _write_active_model_config(
        install_root,
        filename="Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    selection_path = install_root / "config" / "runtime-selection.json"
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(json.dumps({"runtime": "llama.cpp"}), encoding="utf-8")
    _write_runtime_log(
        install_root,
        "\n".join(
            [
                "load_tensors: offloaded 43/43 layers to GPU",
                "llama_kv_cache:      CUDA0 KV buffer size =  2048.00 MiB",
                "llama_kv_cache:      CUDA0 KV buffer size =   100.00 MiB",
                "sched_reserve:      CUDA0 compute buffer size =   517.00 MiB",
                "server: restarting runtime",
                "load_tensors: offloaded 35/35 layers to GPU",
                "llama_kv_cache:      CUDA0 KV buffer size =   768.00 MiB",
                "llama_kv_cache:      CUDA0 KV buffer size =    32.00 MiB",
                "sched_reserve:      CUDA0 compute buffer size =   275.02 MiB",
            ]
        ),
    )

    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service._runtime_binary_supports_flag",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service._detect_nvidia_total_memory_mib",
        lambda: 12 * 1024,
    )
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
    diagnostics = payload["runtimeDiagnostics"]
    assert diagnostics["confirmedGpuLayers"] == 35
    assert diagnostics["kvBufferMiB"] == 800.0
    assert diagnostics["computeBufferMiB"] == 275.02


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


def test_server_restart_route_stops_then_starts_runtime(
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
    steps: list[str] = []

    def fake_stop(config=None):
        steps.append("stop")
        return {
            "status": "ok",
            "action": "stop-server",
            "summary": "Runtime server je zaustavljen.",
            "details": {"returncode": 0, "stdout": "", "stderr": ""},
        }

    def fake_start(config=None):
        steps.append("start")
        return {
            "status": "ok",
            "action": "start-server",
            "summary": "Runtime server je restartovan sa novim context podešavanjem.",
            "details": {"returncode": 0, "stdout": "", "stderr": ""},
        }

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.stop_server",
        fake_stop,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.server_service.start_server",
        fake_start,
    )

    client = TestClient(app)
    response = client.post("/api/server/restart")

    assert response.status_code == 200
    payload = response.json()
    assert steps == ["stop", "start"]
    assert payload["status"] == "ok"
    assert payload["action"] == "restart-server"
    assert "restartovan" in payload["summary"]


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
