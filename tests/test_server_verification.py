import json
from pathlib import Path
from unittest.mock import patch

from local_ai_control_center_installer.server_verification import (
    _cleanup_server_process,
    apply_server_verification,
    probe_server_health,
    stop_server_process,
)
from local_ai_control_center_installer.runtime_bootstrap import (
    _write_runtime_endpoint_config,
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


def _write_runtime_endpoint_fixture(
    install_root: Path,
    *,
    port: int = 8080,
) -> Path:
    return _write_runtime_endpoint_config(
        install_root / "config" / "runtime-endpoint.json",
        port=port,
    )


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
    install_root = tmp_path / "install-root"
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "llama-server.exe").write_text("", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        install_root=str(install_root),
        active_model_config_path=str(tmp_path / "config" / "missing-active-model.json"),
        runtime_artifact_path=str(runtime_dir),
        runtime_endpoint_config_path=str(
            _write_runtime_endpoint_fixture(install_root)
        ),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"


def test_apply_server_verification_fails_when_active_model_path_is_missing_from_config(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
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
        install_root=str(install_root),
        active_model_config_path=str(active_model_config_path),
        runtime_artifact_path=str(runtime_dir),
        runtime_endpoint_config_path=str(
            _write_runtime_endpoint_fixture(install_root)
        ),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"


def test_apply_server_verification_fails_when_llama_server_exe_is_missing(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
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
        install_root=str(install_root),
        active_model_config_path=str(active_model_config_path),
        runtime_artifact_path=str(tmp_path / "missing-runtime"),
        runtime_endpoint_config_path=str(
            _write_runtime_endpoint_fixture(install_root)
        ),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"


def test_apply_server_verification_fails_when_active_model_path_is_a_directory(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
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
        install_root=str(install_root),
        active_model_config_path=str(active_model_config_path),
        runtime_artifact_path=str(runtime_dir),
        runtime_endpoint_config_path=str(
            _write_runtime_endpoint_fixture(install_root)
        ),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"


def test_apply_server_verification_uses_persisted_managed_runtime_port(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path, managed_port=39281)
    process = FakeProcess([None, None, None, None, None, None])
    health_states = iter(["loading", "ready"])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: next(health_states),
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.3, 0.6, 0.9, 1.1, 1.2, 1.3]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "ready"
    assert updated.verified_server_port == 39281
    assert updated.verified_server_url == "http://127.0.0.1:39281"


def test_apply_server_verification_fails_when_foreign_process_owns_managed_port(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path, managed_port=39281)

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        port_is_free=lambda host, port: False,
        is_managed_runtime_port_owned_by_installation=(
            lambda port, server_executable, install_root: False
        ),
        process_factory=lambda command, log_path: (_ for _ in ()).throw(
            AssertionError("foreign-owned managed port should not start a new process")
        ),
        health_probe=lambda base_url: "ready",
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.verified_server_port == 39281
    assert updated.verified_server_url == "http://127.0.0.1:39281"
    assert updated.failing_step == "server-port-bind"
    assert "occupied by another process" in (updated.error_message or "").lower()


def test_apply_server_verification_reuses_same_owner_managed_runtime_when_requested(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path, managed_port=39281)
    health_states = iter(["ready"])
    reused_health_urls: list[str] = []
    stop_port_owner_calls = 0

    def _health_probe(base_url: str) -> str:
        reused_health_urls.append(base_url)
        return next(health_states)

    def _stop_port_owner(*args, **kwargs) -> bool:
        nonlocal stop_port_owner_calls
        stop_port_owner_calls += 1
        return True

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        port_is_free=lambda host, port: False,
        is_managed_runtime_port_owned_by_installation=(
            lambda port, server_executable, install_root: True
        ),
        stop_managed_runtime_on_port=_stop_port_owner,
        process_factory=lambda command, log_path: (_ for _ in ()).throw(
            AssertionError("same-owner reuse should not spawn a new process")
        ),
        health_probe=_health_probe,
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 1.1, 1.2]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "ready"
    assert updated.server_process_status == "ready"
    assert updated.server_health_status == "ready"
    assert reused_health_urls == ["http://127.0.0.1:39281"]
    assert stop_port_owner_calls == 0


def test_apply_server_verification_restarts_same_owner_managed_runtime_when_reuse_is_disabled(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path, managed_port=39281)
    process = FakeProcess([None, None, None, None, None, None])
    health_states = iter(["loading", "ready"])
    events: list[str] = []

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        port_is_free=lambda host, port: False,
        is_managed_runtime_port_owned_by_installation=(
            lambda port, server_executable, install_root: True
        ),
        stop_managed_runtime_on_port=lambda port, server_executable, install_root: (
            events.append("stop-owner") or True
        ),
        reuse_existing_managed_runtime=False,
        process_factory=lambda command, log_path: events.append("start")
        or process,
        health_probe=lambda base_url: next(health_states),
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.3, 0.6, 0.9, 1.1, 1.2, 1.3]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "ready"
    assert updated.server_process_status == "ready"
    assert updated.server_health_status == "ready"
    assert updated.verified_server_port == 39281
    assert events == ["stop-owner", "start"]


def test_apply_server_verification_marks_ready_after_healthy_start_and_clean_stop(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, None, None, None, None, None])
    health_states = iter(["loading", "ready"])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: next(health_states),
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.3, 0.6, 0.9, 1.1, 1.2, 1.3]),
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
    process = FakeProcess([None, None, None, None, None, None, None])
    health_states = iter(["loading", "loading", "ready"])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: next(health_states),
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.3, 0.6, 0.9, 1.1, 1.2, 1.3, 1.4]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "ready"
    assert updated.server_health_status == "ready"


def test_apply_server_verification_tolerates_repeated_now_values_before_ready(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, None, None, None, None, None, None])
    health_states = iter(["loading", "ready"])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: next(health_states),
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.2, 0.8, 1.1, 1.2, 1.2, 1.3]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "ready"
    assert updated.server_process_status == "ready"
    assert updated.server_health_status == "ready"
    assert updated.failing_step is None


def test_probe_server_health_treats_connection_refused_as_failed():
    assert (
        probe_server_health("http://127.0.0.1:1", timeout_seconds=0.01)
        == "failed"
    )


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


def test_apply_server_verification_default_health_probe_tolerates_pre_listen_until_ready(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, None, None, None, None, None])

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"status": "ok"}'

    with patch(
        "local_ai_control_center_installer.server_verification.urlopen",
        side_effect=[
            OSError("connection refused"),
            _Response(),
        ],
    ):
        updated = apply_server_verification(
            session,
            temp_root=tmp_path / "temp-runs",
            select_port=lambda host="127.0.0.1": 8080,
            process_factory=lambda command, log_path: process,
            stop_process=lambda proc: True,
            now_fn=_fake_now([0.0, 0.3, 0.6, 0.9, 1.1, 1.2, 1.3]),
            sleep_fn=lambda _: None,
        )

    assert updated.server_verification_status == "ready"
    assert updated.server_process_status == "ready"
    assert updated.server_health_status == "ready"
    assert updated.failing_step is None


def test_apply_server_verification_marks_process_start_failure_when_process_exits_during_startup_window(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, None, None, 1])
    health_probe_calls = 0

    def _health_probe(base_url: str) -> str:
        nonlocal health_probe_calls
        health_probe_calls += 1
        return "ready"

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=_health_probe,
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.3, 0.6, 0.9, 1.1]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "failed"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-process-start"
    assert health_probe_calls == 0


def test_apply_server_verification_maps_general_start_exception_to_server_process_start(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: (_ for _ in ()).throw(
            RuntimeError("spawn failed")
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


def test_apply_server_verification_maps_invalid_runtime_endpoint_config_to_prerequisites(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    Path(session.runtime_endpoint_config_path).write_text(
        '{"base_url": "", "port": "bad", "installer_managed": true}',
        encoding="utf-8",
    )

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, log_path: None,
        health_probe=lambda base_url: "ready",
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"


def test_apply_server_verification_marks_server_health_failure_after_timeout(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, None, None, None])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: "loading",
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.1, 0.2, 0.3, 30.5]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "ready"
    assert updated.server_health_status == "failed"
    assert updated.failing_step == "server-health"


def test_apply_server_verification_maps_process_death_during_health_polling_to_server_process_start(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, 1])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: "loading",
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0, 0.1, 0.2]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "failed"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-process-start"


def test_apply_server_verification_maps_stop_failure_after_success_to_server_process_stop(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, None, None])
    health_states = iter(["ready"])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: next(health_states),
        stop_process=lambda proc: False,
        now_fn=_fake_now([0.0, 0.1, 0.2]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "ready"
    assert updated.server_health_status == "ready"
    assert updated.failing_step == "server-process-stop"


def test_apply_server_verification_preserves_earlier_failure_when_cleanup_also_fails(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)
    process = FakeProcess([None, None, None, None])

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": 8080,
        process_factory=lambda command, log_path: process,
        health_probe=lambda base_url: "failed",
        stop_process=lambda proc: False,
        now_fn=_fake_now([0.0, 0.1, 0.2, 0.3]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "ready"
    assert updated.server_health_status == "failed"
    assert updated.failing_step == "server-health"
    assert updated.error_message == "failed to stop server verification process"


def test_stop_server_process_returns_false_when_terminate_fails():
    class _TerminateFailsProcess:
        def terminate(self) -> None:
            raise OSError("terminate failed")

        def poll(self) -> int | None:
            return None

        def kill(self) -> None:
            raise AssertionError("kill should not be called after terminate failure")

    assert stop_server_process(_TerminateFailsProcess(), now_fn=_fake_now([0.0])) is False


def test_stop_server_process_returns_false_when_kill_fails_after_timeout():
    class _KillFailsProcess:
        def terminate(self) -> None:
            return None

        def poll(self) -> int | None:
            return None

        def kill(self) -> None:
            raise OSError("kill failed")

    assert (
        stop_server_process(
            _KillFailsProcess(),
            now_fn=_fake_now([0.0, 0.1, 5.0, 5.1]),
            sleep_fn=lambda _: None,
        )
        is False
    )


def test_stop_server_process_returns_true_when_kill_succeeds_after_timeout():
    class _KillSucceedsProcess:
        def __init__(self):
            self.kill_calls = 0
            self._after_kill_poll_results = iter([0])

        def terminate(self) -> None:
            return None

        def poll(self) -> int | None:
            if self.kill_calls == 0:
                return None
            return next(self._after_kill_poll_results, 0)

        def kill(self) -> None:
            self.kill_calls += 1

    process = _KillSucceedsProcess()

    assert (
        stop_server_process(
            process,
            now_fn=_fake_now([0.0, 0.1, 5.0, 5.1, 5.2, 5.3]),
            sleep_fn=lambda _: None,
        )
        is True
    )
    assert process.kill_calls == 1


def test_stop_server_process_waits_for_exit_after_kill_before_returning_true():
    class _KillThenExitProcess:
        def __init__(self):
            self.kill_calls = 0
            self._after_kill_poll_results = iter([None, 0])
            self.after_kill_poll_calls = 0

        def terminate(self) -> None:
            return None

        def poll(self) -> int | None:
            if self.kill_calls == 0:
                return None
            self.after_kill_poll_calls += 1
            return next(self._after_kill_poll_results, 0)

        def kill(self) -> None:
            self.kill_calls += 1

    process = _KillThenExitProcess()

    assert (
        stop_server_process(
            process,
            now_fn=_fake_now([0.0, 0.1, 5.0, 5.1, 5.2, 5.3]),
            sleep_fn=lambda _: None,
        )
        is True
    )
    assert process.kill_calls == 1
    assert process.after_kill_poll_calls >= 2


def test_stop_server_process_returns_false_when_process_stays_alive_after_kill():
    class _KillButStillRunningProcess:
        def __init__(self):
            self.kill_calls = 0

        def terminate(self) -> None:
            return None

        def poll(self) -> int | None:
            return None

        def kill(self) -> None:
            self.kill_calls += 1

    process = _KillButStillRunningProcess()

    assert (
        stop_server_process(
            process,
            now_fn=_fake_now([0.0, 0.1, 5.0, 5.1, 5.2, 10.0, 10.1]),
            sleep_fn=lambda _: None,
        )
        is False
    )
    assert process.kill_calls == 1


def test_cleanup_server_process_closes_attached_server_log_handle_on_cleanup_failure():
    class _FakeLogHandle:
        def __init__(self):
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    class _ProcessWithLogHandle:
        pass

    process = _ProcessWithLogHandle()
    log_handle = _FakeLogHandle()
    setattr(process, "_server_log_handle", log_handle)

    assert (
        _cleanup_server_process(process, stop_process=lambda proc: False)
        == "failed to stop server verification process"
    )
    assert log_handle.close_calls == 1


def _fake_now(values: list[float]):
    iterator = iter(values)
    last_value = values[-1]

    def _now() -> float:
        nonlocal last_value
        last_value = next(iterator, last_value)
        return last_value

    return _now


def _build_runtime_ready_session(
    tmp_path: Path,
    *,
    managed_port: int = 8080,
) -> InstallerSession:
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    config_root = install_root / "config"
    model_path = install_root / "models" / "starter.gguf"
    active_model_path = config_root / "active-model.json"
    runtime_endpoint_path = _write_runtime_endpoint_fixture(
        install_root,
        port=managed_port,
    )

    runtime_root.mkdir(parents=True)
    config_root.mkdir(parents=True, exist_ok=True)
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
        runtime_endpoint_config_path=str(runtime_endpoint_path),
    )


def test_apply_server_verification_fails_when_llama_server_exe_is_a_directory(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
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
        install_root=str(install_root),
        active_model_config_path=str(active_model_config_path),
        runtime_artifact_path=str(runtime_dir),
        runtime_endpoint_config_path=str(
            _write_runtime_endpoint_fixture(install_root)
        ),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"
