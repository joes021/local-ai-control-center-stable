import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.control_center_backend.services.updates_service import (
    load_update_progress_payload,
    run_update_install_worker,
)
from local_ai_control_center_installer.downloads import DownloadProgress


def _write_install_report(install_root: Path, version: str) -> None:
    report_path = install_root / "logs" / "install-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps({"product_version": version}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _latest_release(version: str = "0.4.5") -> dict[str, object]:
    return {
        "version": version,
        "tag_name": f"v{version}",
        "html_url": f"https://github.com/joes021/local-ai-control-center-stable/releases/tag/v{version}",
        "installer_asset_name": f"LocalAIControlCenterSetup-v{version}.exe",
        "installer_download_url": f"https://github.com/joes021/local-ai-control-center-stable/releases/download/v{version}/LocalAIControlCenterSetup-v{version}.exe",
        "installer_size_bytes": 2 * 1024 * 1024 * 1024,
    }


def test_updates_check_route_reports_available_update_and_persists_progress(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_install_report(install_root, "0.4.4")
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.updates_service.fetch_latest_release_metadata",
        lambda: _latest_release("0.4.5"),
    )

    client = TestClient(app)
    response = client.get("/api/updates/check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "0.4.5" in payload["summary"]

    progress = client.get("/api/updates/progress").json()
    assert progress["status"] == "available"
    assert progress["latestVersion"] == "0.4.5"
    assert progress["currentVersion"] == "0.4.4"
    assert progress["targetPath"].endswith("LocalAIControlCenterSetup-v0.4.5.exe")


def test_updates_check_route_reports_up_to_date_when_latest_matches_current(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_install_report(install_root, "0.4.4")
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.updates_service.fetch_latest_release_metadata",
        lambda: _latest_release("0.4.4"),
    )

    client = TestClient(app)
    response = client.get("/api/updates/check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "najnoviju" in payload["summary"].lower()

    progress = client.get("/api/updates/progress").json()
    assert progress["status"] == "up-to-date"
    assert progress["isActive"] is False
    assert progress["latestVersion"] == "0.4.4"


def test_updates_install_route_spawns_worker_and_writes_starting_progress(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_install_report(install_root, "0.4.4")
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.updates_service.fetch_latest_release_metadata",
        lambda: _latest_release("0.4.5"),
    )

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 4321

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.updates_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.updates_service._is_process_alive",
        lambda pid: True,
    )

    client = TestClient(app)
    response = client.post("/api/updates/install")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert "0.4.5" in payload["summary"]

    progress = load_update_progress_payload()
    assert progress["status"] == "starting"
    assert progress["phase"] == "queued"
    assert progress["isActive"] is True
    assert progress["workerPid"] == 4321
    assert progress["latestVersion"] == "0.4.5"
    assert progress["targetPath"].endswith("LocalAIControlCenterSetup-v0.4.5.exe")

    command = captured["command"]
    assert "-m" in command
    assert (
        "local_ai_control_center_installer.control_center_backend.workers.update_install_worker"
        in command
    )
    assert "--action-id" in command


def test_updates_progress_route_marks_dead_active_worker_as_error(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_install_report(install_root, "0.4.4")
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    progress_path = (
        install_root
        / "config"
        / "control-center"
        / "update-progress.json"
    )
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(
        json.dumps(
            {
                "actionId": "dead-worker",
                "status": "downloading",
                "phase": "download",
                "isActive": True,
                "workerPid": 987654,
                "currentVersion": "0.4.4",
                "latestVersion": "0.4.5",
                "releaseUrl": "https://example.invalid/release",
                "targetPath": str(install_root / "updates" / "LocalAIControlCenterSetup-v0.4.5.exe"),
                "percent": 12.5,
                "downloadedGiB": 0.5,
                "totalGiB": 4.0,
                "speedMBps": 10.0,
                "etaSeconds": 20,
                "message": "Download je u toku.",
                "updatedAt": "2026-05-24T12:00:00+00:00",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.services.updates_service._is_process_alive",
        lambda pid: False,
    )

    client = TestClient(app)
    response = client.get("/api/updates/progress")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["isActive"] is False
    assert "Pokreni update ponovo" in payload["message"]


def test_run_update_install_worker_downloads_installer_and_marks_completed(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_install_report(install_root, "0.4.4")
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    captured: dict[str, object] = {}

    def fake_download(url, destination, *, progress_callback=None, plan_item=None, chunk_size=64 * 1024):
        if progress_callback is not None:
            progress_callback(
                DownloadProgress(
                    key="update",
                    label="installer",
                    current_index=1,
                    total_items=1,
                    bytes_downloaded=1024,
                    total_bytes=2048,
                    eta_seconds=3.0,
                )
            )
        destination.write_bytes(b"installer")
        return destination

    def fake_launch(installer_path: Path, config) -> None:
        captured["installer_path"] = installer_path
        captured["install_root"] = config.install_root

    result = run_update_install_worker(
        "update-123",
        latest_release_fetcher=lambda: _latest_release("0.4.5"),
        download_file=fake_download,
        launch_installer=fake_launch,
    )

    assert result["status"] == "ok"
    progress = load_update_progress_payload()
    assert progress["status"] == "completed"
    assert progress["phase"] == "installer-launched"
    assert progress["isActive"] is False
    assert progress["percent"] == 100.0
    assert Path(progress["targetPath"]).is_file()
    assert captured["installer_path"] == Path(progress["targetPath"])
    assert captured["install_root"] == install_root.resolve()


def test_run_update_install_worker_writes_error_state_on_download_failure(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    _write_install_report(install_root, "0.4.4")
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    result = run_update_install_worker(
        "update-err",
        latest_release_fetcher=lambda: _latest_release("0.4.5"),
        download_file=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("network failed")),
        launch_installer=lambda *args, **kwargs: None,
    )

    assert result["status"] == "error"
    progress = load_update_progress_payload()
    assert progress["status"] == "error"
    assert progress["isActive"] is False
    assert "network failed" in progress["message"]
