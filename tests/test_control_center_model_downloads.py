import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.control_center_backend.services.models_service import (
    _write_download_progress,
)
from local_ai_control_center_installer.control_center_backend.config import get_config
from local_ai_control_center_installer.downloads import DownloadProgress
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


def _write_custom_registry(install_root: Path, models: list[dict[str, object]]) -> None:
    registry_path = install_root / "config" / "control-center" / "custom-models.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps({"models": models}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_model_download_route_persists_completed_progress_and_installed_state(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_active_model_config(
        install_root,
        model_id="recommended-6gb",
        model_path=install_root / "models" / "recommended-6gb" / "gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    _write_custom_registry(
        install_root,
        [
            {
                "id": "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0",
                "label": "Qwen 0.6B",
                "filename": "Qwen3-0.6B-Q8_0.gguf",
                "family": "Qwen",
                "source": "huggingface",
                "repo": "Qwen/Qwen3-0.6B-GGUF",
                "download_url": "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf",
            }
        ],
    )
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    def fake_download(url: str, destination: Path, *, progress_callback=None):
        if progress_callback is not None:
            progress_callback(
                DownloadProgress(
                    key="download",
                    label="Qwen 0.6B",
                    current_index=1,
                    total_items=1,
                    bytes_downloaded=0,
                    total_bytes=10,
                    eta_seconds=None,
                )
            )
            progress_callback(
                DownloadProgress(
                    key="download",
                    label="Qwen 0.6B",
                    current_index=1,
                    total_items=1,
                    bytes_downloaded=10,
                    total_bytes=10,
                    eta_seconds=0.0,
                )
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"hf-content")
        return destination

    def inline_spawn(model_id: str, config):
        from local_ai_control_center_installer.control_center_backend.services.models_service import (
            run_model_download_worker,
        )

        run_model_download_worker(model_id, config=config, download_file=fake_download)
        return type("FakeProcess", (), {"pid": 9911})()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.models_service._spawn_model_download_worker",
        inline_spawn,
    )

    client = TestClient(app)
    response = client.post(
        "/api/models/download",
        json={"modelId": "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    progress_response = client.get("/api/models/download-progress")
    assert progress_response.status_code == 200
    progress_payload = progress_response.json()
    assert progress_payload["status"] == "completed"
    assert progress_payload["isActive"] is False
    assert progress_payload["modelId"] == "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0"
    assert progress_payload["percent"] == 100.0

    models_response = client.get("/api/models")
    assert models_response.status_code == 200
    payload = models_response.json()
    hf_model = payload["huggingFace"][0]
    assert hf_model["installed"] is True
    assert hf_model["installedSizeGiB"] is not None
    assert Path(hf_model["resolvedPath"]).is_file()


def test_model_download_route_surfaces_worker_failure_in_progress_payload(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_active_model_config(
        install_root,
        model_id="recommended-6gb",
        model_path=install_root / "models" / "recommended-6gb" / "gemma-4-E4B-it-Q4_K_M.gguf",
    )
    _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=39281,
    )
    _write_custom_registry(
        install_root,
        [
            {
                "id": "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0",
                "label": "Qwen 0.6B",
                "filename": "Qwen3-0.6B-Q8_0.gguf",
                "family": "Qwen",
                "source": "huggingface",
                "repo": "Qwen/Qwen3-0.6B-GGUF",
                "download_url": "https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q8_0.gguf",
            }
        ],
    )
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    def failing_download(url: str, destination: Path, *, progress_callback=None):
        raise OSError("simulated download failure")

    def inline_spawn(model_id: str, config):
        from local_ai_control_center_installer.control_center_backend.services.models_service import (
            run_model_download_worker,
        )

        run_model_download_worker(model_id, config=config, download_file=failing_download)
        return type("FakeProcess", (), {"pid": 9912})()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.models_service._spawn_model_download_worker",
        inline_spawn,
    )

    client = TestClient(app)
    response = client.post(
        "/api/models/download",
        json={"modelId": "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    progress_response = client.get("/api/models/download-progress")
    progress_payload = progress_response.json()
    assert progress_payload["status"] == "error"
    assert progress_payload["isActive"] is False
    assert "simulated download failure" in progress_payload["message"]


def test_browser_download_route_persists_completed_progress_and_installed_state(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
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

    def fake_download(url: str, destination: Path, *, progress_callback=None):
        if progress_callback is not None:
            progress_callback(
                DownloadProgress(
                    key="download",
                    label="Qwen 0.6B",
                    current_index=1,
                    total_items=1,
                    bytes_downloaded=0,
                    total_bytes=10,
                    eta_seconds=None,
                )
            )
            progress_callback(
                DownloadProgress(
                    key="download",
                    label="Qwen 0.6B",
                    current_index=1,
                    total_items=1,
                    bytes_downloaded=10,
                    total_bytes=10,
                    eta_seconds=0.0,
                )
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"hf-content")
        return destination

    def inline_spawn(model_id: str, config):
        from local_ai_control_center_installer.control_center_backend.services.models_service import (
            run_model_download_worker,
        )

        run_model_download_worker(model_id, config=config, download_file=fake_download)
        return type("FakeProcess", (), {"pid": 9913})()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.models_service._spawn_model_download_worker",
        inline_spawn,
    )

    client = TestClient(app)
    response = client.post(
        "/api/browser/catalog/download",
        json={
            "source": "huggingface",
            "repoId": "Qwen/Qwen3-0.6B-GGUF",
            "filename": "Qwen3-0.6B-Q8_0.gguf",
            "label": "Qwen 0.6B",
            "family": "Qwen",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    progress_response = client.get("/api/models/download-progress")
    assert progress_response.status_code == 200
    progress_payload = progress_response.json()
    assert progress_payload["status"] == "completed"
    assert progress_payload["isActive"] is False
    assert progress_payload["modelId"] == "huggingface-qwen-qwen3-0-6b-gguf-qwen3-0-6b-q8-0"
    assert progress_payload["percent"] == 100.0

    models_response = client.get("/api/models")
    assert models_response.status_code == 200
    payload = models_response.json()
    hf_model = payload["huggingFace"][0]
    assert hf_model["installed"] is True
    assert hf_model["installedSizeGiB"] is not None
    assert Path(hf_model["resolvedPath"]).is_file()


def test_browser_download_route_surfaces_worker_failure_in_progress_payload(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
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

    def failing_download(url: str, destination: Path, *, progress_callback=None):
        raise OSError("simulated browser download failure")

    def inline_spawn(model_id: str, config):
        from local_ai_control_center_installer.control_center_backend.services.models_service import (
            run_model_download_worker,
        )

        run_model_download_worker(model_id, config=config, download_file=failing_download)
        return type("FakeProcess", (), {"pid": 9914})()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.models_service._spawn_model_download_worker",
        inline_spawn,
    )

    client = TestClient(app)
    response = client.post(
        "/api/browser/catalog/download",
        json={
            "source": "huggingface",
            "repoId": "Qwen/Qwen3-0.6B-GGUF",
            "filename": "Qwen3-0.6B-Q8_0.gguf",
            "label": "Qwen 0.6B",
            "family": "Qwen",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    progress_response = client.get("/api/models/download-progress")
    progress_payload = progress_response.json()
    assert progress_payload["status"] == "error"
    assert progress_payload["isActive"] is False
    assert "simulated browser download failure" in progress_payload["message"]


def test_download_progress_marks_stale_active_snapshot_as_error(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    progress_path = install_root / "config" / "control-center" / "model-download-progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        json.dumps(
            {
                "status": "downloading",
                "isActive": True,
                "modelId": "unsloth-qwen-iq2-xxs",
                "fileName": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
                "source": "unsloth",
                "percent": 0.4,
                "downloadedGiB": 0.04,
                "totalGiB": 10.02,
                "speedMBps": 40.7,
                "etaSeconds": 251,
                "message": "Download je u toku",
                "updatedAt": "2026-05-24T00:00:00+00:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    client = TestClient(app)
    response = client.get("/api/models/download-progress")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["isActive"] is False
    assert "Pokreni download ponovo" in payload["message"]

    persisted = json.loads(progress_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "error"
    assert persisted["isActive"] is False


def test_write_download_progress_keeps_stronger_active_snapshot_for_same_model(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    _write_download_progress(
        config,
        {
            "status": "downloading",
            "isActive": True,
            "modelId": "unsloth-qwen",
            "fileName": "Qwen.gguf",
            "source": "unsloth",
            "percent": 12.4,
            "downloadedGiB": 1.24,
            "totalGiB": 10.0,
            "speedMBps": 48.2,
            "etaSeconds": 201,
            "message": "Download je u toku",
            "updatedAt": "2026-05-24T01:00:00+00:00",
        },
    )

    _write_download_progress(
        config,
        {
            "status": "starting",
            "isActive": True,
            "modelId": "unsloth-qwen",
            "fileName": "Qwen.gguf",
            "source": "unsloth",
            "percent": None,
            "downloadedGiB": None,
            "totalGiB": None,
            "speedMBps": None,
            "etaSeconds": None,
            "message": "Download je u toku",
            "updatedAt": "2026-05-24T01:00:01+00:00",
        },
    )

    persisted = json.loads(config.model_download_progress_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "downloading"
    assert persisted["percent"] == 12.4
    assert persisted["downloadedGiB"] == 1.24
    assert persisted["totalGiB"] == 10.0
    assert persisted["speedMBps"] == 48.2
    assert persisted["etaSeconds"] == 201
