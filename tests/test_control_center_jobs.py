from pathlib import Path

from local_ai_control_center_installer.control_center_backend.config import get_config


def test_control_center_config_exposes_jobs_registry_path(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    config = get_config()

    assert config.jobs_registry_path == install_root / "config" / "control-center" / "jobs-registry.json"


def test_jobs_service_save_run_and_delete_job(tmp_path: Path, monkeypatch):
    from local_ai_control_center_installer.control_center_backend.services import jobs_service

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))

    observed_calls: list[tuple[str, dict[str, object]]] = []

    def fake_runner(job: dict[str, object]) -> dict[str, object]:
        observed_calls.append((str(job.get("kind")), job))
        return {
            "status": "ok",
            "summary": f"Runner executed {job.get('name')}",
            "details": {"checked": True},
        }

    monkeypatch.setitem(jobs_service._JOB_RUNNERS, "health-check", fake_runner)

    initial = jobs_service.load_jobs_summary()
    assert initial["jobs"] == []
    assert any(item["id"] == "health-check" for item in initial["availableKinds"])

    save_result = jobs_service.save_job(
        {
            "name": "Hourly health",
            "kind": "health-check",
            "intervalMinutes": 30,
            "enabled": True,
        }
    )
    assert save_result["status"] == "ok"
    job_id = save_result["job"]["id"]
    assert save_result["job"]["kind"] == "health-check"
    assert save_result["job"]["intervalMinutes"] == 30

    summary = jobs_service.load_jobs_summary()
    assert summary["jobCount"] == 1
    assert summary["jobs"][0]["name"] == "Hourly health"

    run_result = jobs_service.run_job_now(job_id)
    assert run_result["status"] == "ok"
    assert run_result["job"]["lastStatus"] == "ok"
    assert observed_calls and observed_calls[0][0] == "health-check"

    due_result = jobs_service.run_due_jobs()
    assert due_result["status"] == "ok"
    assert due_result["checkedCount"] >= 1

    delete_result = jobs_service.delete_job(job_id)
    assert delete_result["status"] == "ok"

    final_summary = jobs_service.load_jobs_summary()
    assert final_summary["jobs"] == []
