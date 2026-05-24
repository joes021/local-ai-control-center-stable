import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.runtime_bootstrap import (
    _write_runtime_endpoint_config,
)


def _write_runtime_fixture(install_root: Path, *, include_turboquant: bool) -> None:
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "llama-server.exe").write_text("llama", encoding="utf-8")
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
    _write_runtime_endpoint_config(config_root / "runtime-endpoint.json", port=39281)
    if include_turboquant:
        turbo_root = install_root / "tools" / "turboquant" / "windows-x64-cuda12.4"
        turbo_root.mkdir(parents=True, exist_ok=True)
        (turbo_root / "llama-server.exe").write_text("turbo", encoding="utf-8")


def test_runtime_select_route_persists_requested_runtime(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_runtime_fixture(install_root, include_turboquant=True)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.runtime_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )

    client = TestClient(app)
    response = client.post("/api/runtime/select", json={"runtime": "turboquant"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "TurboQuant" in payload["summary"]
    selection_path = (
        install_root / "config" / "control-center" / "runtime-selection.json"
    )
    assert json.loads(selection_path.read_text(encoding="utf-8"))["runtime"] == "turboquant"


def test_runtime_select_route_rejects_missing_turboquant_runtime(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_runtime_fixture(install_root, include_turboquant=False)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.runtime_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )

    client = TestClient(app)
    response = client.post("/api/runtime/select", json={"runtime": "turboquant"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert "TurboQuant" in payload["summary"]


def test_runtime_select_route_rejects_unlaunchable_turboquant_runtime(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_runtime_fixture(install_root, include_turboquant=True)
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.runtime_service.find_runtime_pid",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.status_service.probe_runtime_binary_launchable",
        lambda path: (False, "TurboQuant launch probe failed.")
        if "turboquant" in str(path).lower()
        else (True, "llama.cpp launch probe passed."),
    )

    client = TestClient(app)
    response = client.post("/api/runtime/select", json={"runtime": "turboquant"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert "TurboQuant" in payload["summary"]
    assert "pokrene" in payload["summary"]


def test_runtime_select_route_rolls_back_selection_when_restart_fails(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_runtime_fixture(install_root, include_turboquant=True)
    selection_path = (
        install_root / "config" / "control-center" / "runtime-selection.json"
    )
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(json.dumps({"runtime": "llama.cpp"}), encoding="utf-8")
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    start_calls: list[str] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.runtime_service.find_runtime_pid",
        lambda *args, **kwargs: 4242,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.runtime_service.stop_server",
        lambda config: {
            "status": "ok",
            "action": "stop-server",
            "summary": "Runtime server je zaustavljen.",
            "details": {"returncode": 0, "stdout": "", "stderr": ""},
        },
    )

    def fake_start_server(config):
        start_calls.append(str(config.install_root))
        if len(start_calls) == 1:
            return {
                "status": "error",
                "action": "start-server",
                "summary": "Novi runtime nije uspeo da se pokrene.",
                "details": {"returncode": 1, "stdout": "", "stderr": "Novi runtime nije uspeo da se pokrene."},
            }
        return {
            "status": "ok",
            "action": "start-server",
            "summary": "Prethodni runtime je vracen.",
            "details": {"returncode": 0, "stdout": "", "stderr": ""},
        }

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.runtime_service.start_server",
        fake_start_server,
    )

    client = TestClient(app)
    response = client.post("/api/runtime/select", json={"runtime": "turboquant"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert "vracen" in payload["summary"].lower()
    assert json.loads(selection_path.read_text(encoding="utf-8"))["runtime"] == "llama.cpp"
    assert len(start_calls) == 2
