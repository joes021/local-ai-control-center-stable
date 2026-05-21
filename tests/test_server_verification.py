from pathlib import Path

from local_ai_control_center_installer.server_verification import (
    apply_server_verification,
)
from local_ai_control_center_installer.session import InstallerSession


def test_apply_server_verification_skips_when_runtime_payload_is_not_ready(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="failed",
        install_root=str(tmp_path / "install-root"),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "skipped"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"


def test_apply_server_verification_skips_when_bootstrap_is_not_ready(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="failed",
        runtime_payload_status="ready",
        install_root=str(tmp_path / "install-root"),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "skipped"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"


def test_apply_server_verification_fails_when_active_model_config_is_missing(
    tmp_path: Path,
):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "llama-server.exe").write_text("", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        install_root=str(tmp_path / "install-root"),
        active_model_config_path=str(tmp_path / "config" / "missing-active-model.json"),
        runtime_artifact_path=str(runtime_dir),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"


def test_apply_server_verification_fails_when_active_model_path_is_missing_from_config(
    tmp_path: Path,
):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "llama-server.exe").write_text("", encoding="utf-8")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    active_model_config_path = config_dir / "active-model.json"
    active_model_config_path.write_text(
        '{"model_id": "recommended-6gb", "model_path": ""}',
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        install_root=str(tmp_path / "install-root"),
        active_model_config_path=str(active_model_config_path),
        runtime_artifact_path=str(runtime_dir),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"


def test_apply_server_verification_fails_when_llama_server_exe_is_missing(
    tmp_path: Path,
):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    model_path = tmp_path / "models" / "model.gguf"
    model_path.parent.mkdir()
    model_path.write_text("", encoding="utf-8")
    active_model_config_path = config_dir / "active-model.json"
    active_model_config_path.write_text(
        (
            '{"model_id": "recommended-6gb", '
            f'"model_path": "{model_path.as_posix()}"}}'
        ),
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        install_root=str(tmp_path / "install-root"),
        active_model_config_path=str(active_model_config_path),
        runtime_artifact_path=str(tmp_path / "missing-runtime"),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"
