import json
from pathlib import Path

from local_ai_control_center_installer.server_verification import (
    apply_server_verification,
)
from local_ai_control_center_installer.session import InstallerSession


class FakeProcess:
    def __init__(self, poll_results: list[int | None]):
        self._poll_results = iter(poll_results)
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self) -> int | None:
        return next(self._poll_results, None)

    def terminate(self) -> None:
        self.terminate_calls += 1

    def kill(self) -> None:
        self.kill_calls += 1


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


def test_apply_server_verification_fails_when_active_model_path_is_a_directory(
    tmp_path: Path,
):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "llama-server.exe").write_text("", encoding="utf-8")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    model_dir = tmp_path / "models" / "model.gguf"
    model_dir.mkdir(parents=True)
    active_model_config_path = config_dir / "active-model.json"
    active_model_config_path.write_text(
        (
            '{"model_id": "recommended-6gb", '
            f'"model_path": "{model_dir.as_posix()}"}}'
        ),
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


def test_apply_server_verification_marks_ready_after_healthy_start_and_clean_stop(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, None, None])
    health_states = iter(["loading", "ready"])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: next(health_states),
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.1, 0.2, 0.3]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "ready"
    assert updated.server_process_status == "ready"
    assert updated.server_health_status == "ready"
    assert updated.verified_server_port == 8080
    assert updated.verified_server_url == "http://127.0.0.1:8080"
    assert updated.failing_step is None


def test_apply_server_verification_continues_polling_through_loading_503_until_ready(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, None, None, None])
    health_states = iter(["loading", "loading", "ready"])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: next(health_states),
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.1, 0.2, 0.3, 0.4]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "ready"
    assert updated.server_health_status == "ready"


def test_apply_server_verification_marks_process_start_failure_when_process_exits_early(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([1])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: "ready",
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.1]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "failed"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-process-start"


def test_apply_server_verification_maps_subprocess_start_exception_to_server_process_start(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: (_ for _ in ()).throw(
            OSError("spawn failed")
        ),
        health_probe=lambda base_url: "ready",
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.1]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "failed"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-process-start"


def _fake_now(values: list[float]):
    iterator = iter(values)
    last_value = values[-1]

    def _now() -> float:
        nonlocal last_value
        last_value = next(iterator, last_value)
        return last_value

    return _now


def _build_runtime_ready_session(tmp_path: Path) -> InstallerSession:
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    config_root = install_root / "config"
    model_path = install_root / "models" / "starter.gguf"
    active_model_path = config_root / "active-model.json"

    runtime_root.mkdir(parents=True)
    config_root.mkdir(parents=True)
    model_path.parent.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("", encoding="utf-8")
    model_path.write_text("", encoding="utf-8")
    active_model_path.write_text(
        json.dumps(
            {
                "model_id": "recommended-6gb",
                "model_path": str(model_path),
            }
        ),
        encoding="utf-8",
    )

    return InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        install_root=str(install_root),
        active_model_config_path=str(active_model_path),
        runtime_artifact_path=str(runtime_root),
    )


def test_apply_server_verification_fails_when_llama_server_exe_is_a_directory(
    tmp_path: Path,
):
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "llama-server.exe").mkdir()
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
        runtime_artifact_path=str(runtime_dir),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"
