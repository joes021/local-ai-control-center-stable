import json
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def _write_opencode_fixture(install_root: Path) -> None:
    opencode_root = install_root / "tools" / "opencode"
    opencode_root.mkdir(parents=True, exist_ok=True)
    (opencode_root / "opencode.exe").write_text("opencode", encoding="utf-8")
    config_root = install_root / "config" / "opencode"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "managed-config.json").write_text(
        json.dumps(
            {
                "model": "local-lacc/recommended-6gb",
                "enabled_providers": ["local-lacc", "opencode"],
                "provider": {
                    "local-lacc": {"options": {"baseURL": "http://127.0.0.1:39281/v1"}}
                },
            }
        ),
        encoding="utf-8",
    )


def _write_runtime_and_model_prerequisites(install_root: Path) -> None:
    runtime_endpoint_path = install_root / "config" / "runtime-endpoint.json"
    runtime_endpoint_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_endpoint_path.write_text(
        json.dumps(
            {
                "port": 39281,
                "base_url": "http://127.0.0.1:39281",
                "installer_managed": True,
            }
        ),
        encoding="utf-8",
    )
    model_path = install_root / "models" / "local" / "demo.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    active_model_path = install_root / "config" / "active-model.json"
    active_model_path.parent.mkdir(parents=True, exist_ok=True)
    active_model_path.write_text(
        json.dumps({"model_id": "local-demo", "model_path": str(model_path)}),
        encoding="utf-8",
    )


def test_opencode_status_route_reports_packaged_installation(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    _write_runtime_and_model_prerequisites(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_instances",
        lambda executable_path: [],
    )

    client = TestClient(app)
    response = client.get("/api/opencode/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["active"] is False
    assert payload["instanceCount"] == 0
    assert payload["configExists"] is True
    assert payload["configPath"].endswith("config\\opencode\\managed-config.json")
    assert payload["executablePath"].endswith("tools\\opencode\\opencode.exe")
    assert payload["profile"] == "balanced"
    assert payload["canOpen"] is True
    assert payload["openActionLabel"] == "Otvori OpenCode"
    assert payload["openBlockedReason"] == ""
    assert payload["canBootstrap"] is True
    assert payload["bootstrapActionLabel"] == "Reinstall / popravi OpenCode"
    assert payload["bootstrapBlockedReason"] == ""
    assert payload["launchPreview"]["shellLabel"] == "PowerShell"
    assert payload["launchPreview"]["launcherPath"].endswith("Open-OpenCode.cmd")
    assert "cmd.exe /d /k" in payload["launchPreview"]["launcherCommand"]
    assert "$env:OPENCODE_CONFIG" in payload["launchPreview"]["powershellCommand"]
    assert "opencode.exe" in payload["launchPreview"]["powershellCommand"]
    assert "temp 0.8" in payload["launchPreview"]["generationSummary"]
    assert payload["launchPreview"]["managedConfig"]["model"] == "local-lacc/recommended-6gb"
    assert payload["launchPreview"]["managedConfig"]["selectedProvider"] == "local-lacc"
    assert payload["launchPreview"]["managedConfig"]["localProviderBaseUrl"] == "http://127.0.0.1:39281/v1"
    assert payload["launchPreview"]["managedConfig"]["enabledProviders"] == ["local-lacc", "opencode"]


def test_opencode_status_route_reports_app_only_when_runtime_is_not_connected(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_instances",
        lambda executable_path: [
            {
                "pid": 4242,
                "name": "opencode.exe",
                "commandLine": "\"C:\\\\opencode.exe\"",
            }
        ],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.load_runtime_state",
        lambda config: {
            "runtime_live_status": "stopped",
            "runtime_live_reason": "Runtime trenutno nije pokrenut.",
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/opencode/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active"] is True
    assert payload["runtimeConnected"] is False
    assert payload["sessionState"] == "app-only"
    assert "nije pokrenut" in payload["sessionSummary"].lower()
    assert payload["canOpen"] is True
    assert "Pripremi backend" in payload["openActionLabel"]


def test_opencode_status_route_reports_blocked_open_when_executable_is_missing(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    config_root = install_root / "config" / "opencode"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "managed-config.json").write_text("{}", encoding="utf-8")
    _write_runtime_and_model_prerequisites(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)
    response = client.get("/api/opencode/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["canOpen"] is False
    assert payload["openActionLabel"] == "OpenCode nije instaliran"
    assert "nije pronađen" in payload["openBlockedReason"].lower()
    assert payload["canBootstrap"] is True
    assert payload["bootstrapActionLabel"] == "Instaliraj OpenCode"


def test_opencode_bootstrap_route_delegates_to_bootstrap_service(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    captured: dict[str, object] = {}

    def fake_bootstrap(config):
        captured["install_root"] = str(config.install_root)
        return {
            "status": "ok",
            "action": "bootstrap-opencode",
            "summary": "OpenCode je spreman.",
            "details": {
                "returncode": 0,
                "stdout": "ready",
                "stderr": "",
            },
        }

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.opencode.bootstrap_opencode_payload",
        fake_bootstrap,
    )

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_launcher_instances",
        lambda launcher_path: [],
    )

    client = TestClient(app)
    response = client.post("/api/opencode/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["action"] == "bootstrap-opencode"
    assert captured["install_root"] == str(install_root)


def test_bootstrap_opencode_payload_does_not_require_starter_model_for_repair_flow(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.services import opencode_service

    install_root = tmp_path / "install-root"
    _write_runtime_and_model_prerequisites(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    captured: dict[str, object] = {}

    def fake_apply(session, **kwargs):
        captured["download_keys"] = [item.key for item in session.download_plan.items]
        opencode_root = install_root / "tools" / "opencode"
        opencode_root.mkdir(parents=True, exist_ok=True)
        (opencode_root / "opencode.exe").write_text("opencode", encoding="utf-8")
        session.opencode_artifact_status = "ready"
        session.last_successful_step = "opencode-config"
        return session

    monkeypatch.setattr(opencode_service, "apply_opencode_bootstrap", fake_apply)
    monkeypatch.setattr(
        opencode_service,
        "prepare_opencode_launcher",
        lambda config=None, profile="": install_root / "control-center" / "Open-OpenCode.cmd",
    )

    payload = opencode_service.bootstrap_opencode_payload(opencode_service.get_config())

    assert payload["status"] == "ok"
    assert payload["action"] == "bootstrap-opencode"
    assert captured["download_keys"] == ["opencode-artifact"]


def test_opencode_status_route_ignores_instances_from_other_install_roots(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service._query_opencode_processes",
        lambda: [
            {
                "pid": 5151,
                "name": "opencode.exe",
                "commandLine": "\"C:\\\\Users\\\\OtherUser\\\\LocalAIControlCenter\\\\tools\\\\opencode\\\\opencode.exe\"",
            }
        ],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.load_runtime_state",
        lambda config: {
            "runtime_live_status": "started",
            "runtime_live_reason": "Runtime je spreman za novi OpenCode session.",
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/opencode/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active"] is False
    assert payload["instanceCount"] == 0
    assert payload["sessionState"] == "runtime-ready"


def test_opencode_open_route_does_not_treat_foreign_instance_as_local_session(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    captured: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service._query_opencode_processes",
        lambda: [
            {
                "pid": 6161,
                "name": "opencode.exe",
                "commandLine": "\"C:\\\\Users\\\\OtherUser\\\\LocalAIControlCenter\\\\tools\\\\opencode\\\\opencode.exe\"",
            }
        ],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_launcher_instances",
        lambda launcher_path: [],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.ensure_runtime_ready",
        lambda config: {
            "status": "ok",
            "action": "ensure-runtime-ready",
            "summary": "Runtime je spreman za OpenCode.",
            "details": {
                "returncode": 0,
                "stdout": "Runtime je spreman za OpenCode.",
                "stderr": "",
            },
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.post("/api/opencode/open", json={"profile": "balanced"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "pokrenut" in payload["summary"].lower()
    launcher_path = install_root / "control-center" / "Open-OpenCode.cmd"
    assert captured["command"] == ["cmd.exe", "/d", "/k", str(launcher_path)]


def test_opencode_open_route_launches_visible_windows_launcher(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    captured: dict[str, object] = {}
    ensure_calls: list[str] = []

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs

    def fake_ensure_runtime_ready(config):
        ensure_calls.append(str(config.install_root))
        return {
            "status": "ok",
            "action": "ensure-runtime-ready",
            "summary": "Runtime je spreman za OpenCode.",
            "details": {
                "returncode": 0,
                "stdout": "Runtime je spreman za OpenCode.",
                "stderr": "",
            },
        }

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.ensure_runtime_ready",
        fake_ensure_runtime_ready,
        raising=False,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_instances",
        lambda executable_path: [],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_launcher_instances",
        lambda launcher_path: [],
    )

    client = TestClient(app)
    response = client.post("/api/opencode/open", json={"profile": "balanced"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "OpenCode je pokrenut" in payload["summary"]
    assert ensure_calls == [str(install_root)]
    launcher_path = install_root / "control-center" / "Open-OpenCode.cmd"
    assert launcher_path.name == "Open-OpenCode.cmd"
    assert launcher_path.is_file()
    launcher_text = launcher_path.read_text(encoding="utf-8")
    assert "title Local AI Control Center - OpenCode" in launcher_text
    assert "opencode.exe" in launcher_text
    assert "managed-config.json" in launcher_text
    assert 'set "LACC_PROFILE=balanced"' in launcher_text
    assert 'set "LACC_OPENCODE_SECURITY_MODE=strict"' in launcher_text
    assert 'echo OpenCode je završio sa kodom %OPENCODE_EXIT_CODE%.' in launcher_text
    assert "pause" in launcher_text
    assert captured["command"] == [
        "cmd.exe",
        "/d",
        "/k",
        str(launcher_path),
    ]
    assert captured["kwargs"]["cwd"] == str(launcher_path.parent)
    assert captured["kwargs"]["creationflags"] == getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def test_opencode_open_route_returns_error_when_runtime_cannot_be_prepared(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    launch_attempted = False

    def fake_popen(command, **kwargs):
        nonlocal launch_attempted
        launch_attempted = True

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.ensure_runtime_ready",
        lambda config: {
            "status": "error",
            "action": "ensure-runtime-ready",
            "summary": "Runtime nije mogao da se pripremi za OpenCode.",
            "details": {
                "returncode": 1,
                "stdout": "",
                "stderr": "Runtime nije mogao da se pripremi za OpenCode.",
            },
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.post("/api/opencode/open", json={"profile": "balanced"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert "runtime" in payload["summary"].lower()
    assert launch_attempted is False


def test_opencode_open_route_reuses_existing_window_when_runtime_becomes_ready(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    launch_attempted = False

    def fake_popen(command, **kwargs):
        nonlocal launch_attempted
        launch_attempted = True

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_instances",
        lambda executable_path: [
            {
                "pid": 4242,
                "name": "opencode.exe",
                "commandLine": "\"C:\\\\opencode.exe\"",
            }
        ],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.ensure_runtime_ready",
        lambda config: {
            "status": "ok",
            "action": "ensure-runtime-ready",
            "summary": "Runtime je spreman za OpenCode.",
            "details": {
                "returncode": 0,
                "stdout": "Runtime je spreman za OpenCode.",
                "stderr": "",
            },
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.post("/api/opencode/open", json={"profile": "balanced"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "već otvoren" in payload["summary"].lower()
    assert launch_attempted is False


def test_prepare_opencode_launcher_writes_linux_shell_launcher(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.config import ControlCenterConfig
    from local_ai_control_center_installer.control_center_backend.services import opencode_service

    install_root = tmp_path / "install-root"
    config = ControlCenterConfig(
        ui_host="127.0.0.1",
        ui_port=3210,
        install_root=install_root,
        access_mode="local-only",
    )
    opencode_root = install_root / "tools" / "opencode"
    opencode_root.mkdir(parents=True, exist_ok=True)
    executable_path = opencode_root / "opencode"
    executable_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    config_root = install_root / "config" / "opencode"
    config_root.mkdir(parents=True, exist_ok=True)
    managed_config_path = config_root / "managed-config.json"
    managed_config_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        opencode_service,
        "load_opencode_manifest",
        lambda: {
            "opencode_artifact": {
                "install_subdir": "tools/opencode",
                "launch": {"executable_relative_path": "opencode"},
            }
        },
    )

    launcher_path = opencode_service.prepare_opencode_launcher(
        config=config,
        profile="balanced",
        platform="linux",
    )

    launcher_text = launcher_path.read_text(encoding="utf-8")

    assert launcher_path.name == "Open-OpenCode.sh"
    assert launcher_text.startswith("#!/usr/bin/env bash\n")
    assert f'export OPENCODE_CONFIG="{managed_config_path}"' in launcher_text
    assert f'exec "{executable_path}" "$@"' in launcher_text


def test_opencode_open_route_does_not_spawn_new_terminal_when_launcher_is_already_in_progress(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    launch_attempted = False

    def fake_popen(command, **kwargs):
        nonlocal launch_attempted
        launch_attempted = True

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_instances",
        lambda executable_path: [],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_launcher_instances",
        lambda launcher_path: [
            {
                "pid": 9898,
                "name": "cmd.exe",
                "commandLine": f'cmd.exe /d /k "{launcher_path}"',
            }
        ],
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.ensure_runtime_ready",
        lambda config: {
            "status": "ok",
            "action": "ensure-runtime-ready",
            "summary": "Runtime je spreman za OpenCode.",
            "details": {
                "returncode": 0,
                "stdout": "Runtime je spreman za OpenCode.",
                "stderr": "",
            },
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.post("/api/opencode/open", json={"profile": "balanced"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "launch je ve" in payload["summary"].lower()
    assert launch_attempted is False


def test_prepare_opencode_launcher_writes_windows_duplicate_launch_guard(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_control_center_installer.control_center_backend.config import ControlCenterConfig
    from local_ai_control_center_installer.control_center_backend.services import opencode_service

    install_root = tmp_path / "install-root"
    config = ControlCenterConfig(
        ui_host="127.0.0.1",
        ui_port=3210,
        install_root=install_root,
        access_mode="local-only",
    )
    opencode_root = install_root / "tools" / "opencode"
    opencode_root.mkdir(parents=True, exist_ok=True)
    executable_path = opencode_root / "opencode.exe"
    executable_path.write_text("opencode", encoding="utf-8")
    config_root = install_root / "config" / "opencode"
    config_root.mkdir(parents=True, exist_ok=True)
    managed_config_path = config_root / "managed-config.json"
    managed_config_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        opencode_service,
        "load_opencode_manifest",
        lambda: {
            "opencode_artifact": {
                "install_subdir": "tools/opencode",
                "launch": {"executable_relative_path": "opencode.exe"},
            }
        },
    )

    launcher_path = opencode_service.prepare_opencode_launcher(
        config=config,
        profile="balanced",
        platform="win32",
    )

    launcher_text = launcher_path.read_text(encoding="utf-8")

    assert launcher_path.name == "Open-OpenCode.cmd"
    assert "Win32_Process" in launcher_text
    assert str(executable_path) in launcher_text
    assert str(launcher_path) in launcher_text
    assert "OpenCode launch je ve" in launcher_text


def test_opencode_steps_and_settings_routes_persist_panel_managed_values(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_opencode_fixture(install_root)
    model_root = install_root / "models" / "recommended-6gb"
    model_root.mkdir(parents=True, exist_ok=True)
    (model_root / "gemma-4-E4B-it-Q4_K_M.gguf").write_text("model", encoding="utf-8")
    config_root = install_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "active-model.json").write_text(
        json.dumps(
            {
                "model_id": "recommended-6gb",
                "model_path": str(model_root / "gemma-4-E4B-it-Q4_K_M.gguf"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.opencode_service.detect_opencode_instances",
        lambda executable_path: [],
    )

    client = TestClient(app)
    schema_response = client.get("/api/opencode/steps")
    assert schema_response.status_code == 200
    schema_payload = schema_response.json()
    assert schema_payload["builtInPresets"]
    assert schema_payload["currentSteps"]["buildSteps"] == 140

    apply_response = client.post(
        "/api/opencode/settings/apply",
        json={
            "profile": "speed",
            "context": 131072,
            "outputTokens": 4096,
            "workingDirectory": str(tmp_path / "workspace"),
            "buildSteps": 200,
            "planSteps": 150,
            "generalSteps": 120,
            "exploreSteps": 90,
            "securityMode": "open",
            "capabilityMode": "auto-commands",
        },
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["status"] == "ok"

    preset_response = client.post(
        "/api/opencode/steps/presets/save",
        json={
            "name": "My steps",
            "steps": {
                "buildSteps": 200,
                "planSteps": 150,
                "generalSteps": 120,
                "exploreSteps": 90,
            },
        },
    )
    assert preset_response.status_code == 200
    assert preset_response.json()["status"] == "ok"

    status_response = client.get("/api/opencode/status")
    status_payload = status_response.json()
    assert status_payload["workingDirectory"] == str(tmp_path / "workspace")
    assert status_payload["securityMode"] == "open"
    assert status_payload["capabilityMode"] == "auto-commands"
    assert status_payload["buildSteps"] == 200
    assert status_payload["profile"] == "speed"

    updated_schema = client.get("/api/opencode/steps").json()
    assert len(updated_schema["userPresets"]) == 1
    preset_id = updated_schema["userPresets"][0]["id"]

    delete_response = client.post(
        "/api/opencode/steps/presets/delete",
        json={"presetId": preset_id},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"
