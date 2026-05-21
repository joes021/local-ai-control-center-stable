import json
from pathlib import Path
from subprocess import TimeoutExpired

import pytest

from local_ai_control_center_installer.opencode_verification import (
    apply_opencode_verification,
)
from local_ai_control_center_installer.session import InstallerSession


def _build_manifest(
    *,
    extra_env: dict[str, str] | None = None,
    executable_relative_path: str = "opencode.exe",
) -> dict:
    return {
        "opencode_artifact": {
            "id": "windows-opencode",
            "launch": {
                "executable_relative_path": executable_relative_path,
                "verification_args": ["--pure", "models"],
                "extra_env": extra_env or {},
            },
        }
    }


def _build_malformed_manifest(launch) -> dict:
    return {
        "opencode_artifact": {
            "id": "windows-opencode",
            "launch": launch,
        }
    }


def _write_active_model_config(
    path: Path,
    *,
    model_id: str = "recommended-6gb",
    model_path: Path | None = None,
) -> Path:
    if model_path is None:
        model_path = path.parent / "models" / f"{model_id}.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "model_id": model_id,
                "model_path": str(model_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _write_managed_config(path: Path, *, verified_server_url: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "providers": {
                    "local-lacc": {
                        "options": {"baseURL": f"{verified_server_url}/v1"}
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _build_ready_session(tmp_path: Path) -> InstallerSession:
    install_root = tmp_path / "install-root"
    active_model_config_path = _write_active_model_config(
        install_root / "config" / "active-model.json"
    )
    opencode_root = install_root / "tools" / "opencode"
    opencode_root.mkdir(parents=True, exist_ok=True)
    (opencode_root / "opencode.exe").write_text("binary", encoding="utf-8")
    managed_config_path = _write_managed_config(
        install_root / "config" / "opencode" / "managed-config.json",
        verified_server_url="http://127.0.0.1:8080",
    )
    return InstallerSession(
        started_at="2026-05-22T10:11:12",
        opencode_artifact_status="ready",
        opencode_verification_status="failed",
        opencode_process_status="failed",
        opencode_connection_status="failed",
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(active_model_config_path),
        opencode_artifact_path=str(opencode_root),
        opencode_config_path=str(managed_config_path),
        failing_step="earlier-step",
        error_message="earlier error",
    )


def _build_nested_executable_session(tmp_path: Path) -> InstallerSession:
    session = _build_ready_session(tmp_path)
    artifact_root = Path(session.opencode_artifact_path)
    (artifact_root / "opencode.exe").unlink()
    nested_executable = artifact_root / "bin" / "opencode.exe"
    nested_executable.parent.mkdir(parents=True, exist_ok=True)
    nested_executable.write_text("binary", encoding="utf-8")
    return session


class FakeProcess:
    def __init__(
        self,
        *,
        stdout: str = "",
        returncode: int = 0,
        timeout: bool = False,
    ) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.timeout = timeout
        self.communicate_timeouts: list[float | None] = []

    def communicate(self, timeout=None):
        self.communicate_timeouts.append(timeout)
        if self.timeout:
            raise TimeoutExpired("opencode", timeout, output=self.stdout)
        return self.stdout, None


class PollSequenceProcess(FakeProcess):
    def __init__(self, poll_values: list[int | None], **kwargs) -> None:
        super().__init__(**kwargs)
        self.poll_values = poll_values
        self.poll_calls = 0

    def poll(self):
        index = min(self.poll_calls, len(self.poll_values) - 1)
        self.poll_calls += 1
        return self.poll_values[index]

    def terminate(self):
        raise OSError("already exited")

    def kill(self):
        raise AssertionError("kill should not be needed when process already exited")


def test_apply_opencode_verification_skips_when_artifact_not_ready(tmp_path: Path):
    session = InstallerSession(
        opencode_artifact_status="failed",
        opencode_verification_status="failed",
        opencode_process_status="failed",
        opencode_connection_status="failed",
        failing_step="opencode-artifact",
        error_message="artifact missing",
    )

    updated = apply_opencode_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.opencode_verification_status == "skipped"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-artifact"
    assert updated.error_message == "artifact missing"


@pytest.mark.parametrize(
    ("case_name", "mutate_session", "manifest_loader"),
    [
        (
            "missing verified server url",
            lambda session: setattr(session, "verified_server_url", None),
            lambda: _build_manifest(),
        ),
        (
            "unreadable active model config",
            lambda session: Path(session.active_model_config_path).write_text(
                "{", encoding="utf-8"
            ),
            lambda: _build_manifest(),
        ),
        (
            "missing active model file",
            lambda session: Path(
                json.loads(
                    Path(session.active_model_config_path).read_text(
                        encoding="utf-8"
                    )
                )["model_path"]
            ).unlink(),
            lambda: _build_manifest(),
        ),
        (
            "missing opencode executable",
            lambda session: Path(session.opencode_artifact_path, "opencode.exe").unlink(),
            lambda: _build_manifest(),
        ),
        (
            "missing managed config",
            lambda session: Path(session.opencode_config_path).unlink(),
            lambda: _build_manifest(),
        ),
        (
            "manifest reload failure",
            lambda session: None,
            lambda: (_ for _ in ()).throw(ValueError("bad manifest")),
        ),
    ],
)
def test_apply_opencode_verification_fails_prerequisites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_name: str,
    mutate_session,
    manifest_loader,
):
    session = _build_ready_session(tmp_path)
    mutate_session(session)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        manifest_loader,
    )

    updated = apply_opencode_verification(session, temp_root=tmp_path / "temp-runs")

    assert case_name
    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-verification-prerequisites"


def test_apply_opencode_verification_success_path_and_log_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    process = FakeProcess(stdout="booting\nlocal-lacc/recommended-6gb\n", returncode=0)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    captured: dict[str, object] = {}

    def process_factory(command, *, cwd, env, log_path):
        captured["log_path"] = log_path
        return process

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=process_factory,
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "ready"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "ready"
    assert updated.failing_step is None
    assert updated.error_message is None
    assert (
        updated.verified_opencode_command
        == f"{Path(session.opencode_artifact_path) / 'opencode.exe'} --pure models local-lacc"
    )
    assert updated.opencode_log_path is not None
    assert (
        Path(updated.opencode_log_path).read_text(encoding="utf-8")
        == "booting\nlocal-lacc/recommended-6gb\n"
    )
    assert captured["log_path"] == Path(updated.opencode_log_path)
    assert "2026-05-22T10-11-12" in updated.opencode_log_path


def test_apply_opencode_verification_uses_empty_temp_working_directory_and_expected_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(
            extra_env={
                "CUSTOM_FLAG": "enabled",
                "OPENCODE_CONFIG": "manifest-overridden",
                "OPENCODE_DISABLE_MODELS_FETCH": "false",
            }
        ),
    )

    def process_factory(command, *, cwd, env, log_path):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["log_path"] = log_path
        return FakeProcess(stdout="local-lacc/recommended-6gb\n", returncode=0)

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=process_factory,
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "ready"
    assert captured["command"] == [
        str(Path(session.opencode_artifact_path) / "opencode.exe"),
        "--pure",
        "models",
        "local-lacc",
    ]
    assert captured["log_path"] == Path(updated.opencode_log_path)
    working_directory = Path(captured["cwd"])
    assert working_directory.exists()
    assert list(working_directory.iterdir()) == []

    env = captured["env"]
    assert env["CUSTOM_FLAG"] == "enabled"
    assert env["OPENCODE_CONFIG"] == session.opencode_config_path
    assert env["OPENCODE_DISABLE_MODELS_FETCH"] == "true"

    embedded_config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    assert embedded_config["model"] == "local-lacc/recommended-6gb"
    assert (
        embedded_config["providers"]["local-lacc"]["options"]["baseURL"]
        == "http://127.0.0.1:8080/v1"
    )


def test_apply_opencode_verification_maps_working_directory_failure_to_process_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification._make_working_directory",
        lambda run_dir: (_ for _ in ()).throw(OSError("temp root unavailable")),
    )

    updated = apply_opencode_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "failed"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-process-start"
    assert updated.error_message == "temp root unavailable"


def test_apply_opencode_verification_maps_log_write_failure_without_crashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification._write_log_text",
        lambda log_path, text: (_ for _ in ()).throw(OSError("disk full")),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="local-lacc/recommended-6gb\n",
            returncode=0,
        ),
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "failed"
    assert updated.failing_step == "opencode-connection"
    assert "disk full" in updated.error_message


def test_apply_opencode_verification_maps_invalid_utf8_managed_config_to_prerequisites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    Path(session.opencode_config_path).write_bytes(b"\x80\x81broken")

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="local-lacc/recommended-6gb\n",
            returncode=0,
        ),
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-verification-prerequisites"


def test_apply_opencode_verification_rejects_near_match_model_token_in_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="local-lacc/recommended-6gb-q4\n",
            returncode=0,
        ),
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "failed"
    assert updated.failing_step == "opencode-connection"


def test_apply_opencode_verification_rejects_near_match_base_url_in_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    _write_managed_config(
        Path(session.opencode_config_path),
        verified_server_url="http://127.0.0.1:8080/v10".removesuffix("/v10"),
    )
    Path(session.opencode_config_path).write_text(
        json.dumps(
            {
                "providers": {
                    "local-lacc": {
                        "options": {"baseURL": "http://127.0.0.1:8080/v10"}
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="local-lacc/recommended-6gb\n",
            returncode=0,
        ),
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "failed"
    assert updated.failing_step == "opencode-connection"


def test_apply_opencode_verification_resolves_manifest_nested_executable_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_nested_executable_session(tmp_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(executable_relative_path="bin/opencode.exe"),
    )

    def process_factory(command, *, cwd, env, log_path):
        captured["command"] = command
        return FakeProcess(stdout="local-lacc/recommended-6gb\n", returncode=0)

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=process_factory,
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "ready"
    assert captured["command"][0] == str(
        Path(session.opencode_artifact_path) / "bin" / "opencode.exe"
    )


def test_apply_opencode_verification_manifest_extra_env_cannot_override_config_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(
            extra_env={
                "OPENCODE_CONFIG_CONTENT": json.dumps({"model": "wrong/provider"})
            }
        ),
    )

    def process_factory(command, *, cwd, env, log_path):
        captured["env"] = env
        return FakeProcess(stdout="local-lacc/recommended-6gb\n", returncode=0)

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=process_factory,
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "ready"
    embedded_config = json.loads(captured["env"]["OPENCODE_CONFIG_CONTENT"])
    assert embedded_config["model"] == "local-lacc/recommended-6gb"


@pytest.mark.parametrize(
    "manifest_loader",
    [
        lambda: _build_manifest(extra_env={}) | {
            "opencode_artifact": {"id": "windows-opencode"}
        },
        lambda: _build_malformed_manifest(None),
        lambda: _build_malformed_manifest({}),
        lambda: _build_malformed_manifest(
            {
                "verification_args": ["models"],
                "extra_env": {},
            }
        ),
        lambda: _build_malformed_manifest(
            {
                "verification_args": ["--pure", "models", "local-lacc"],
                "extra_env": {},
            }
        ),
        lambda: _build_malformed_manifest(
            {
                "verification_args": ["--pure", "models"],
                "extra_env": [],
            }
        ),
    ],
)
def test_apply_opencode_verification_maps_malformed_manifest_launch_contract_to_prerequisites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest_loader,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        manifest_loader,
    )

    updated = apply_opencode_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-verification-prerequisites"


def test_apply_opencode_verification_fails_on_connection_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="other-provider/not-it\n",
            returncode=0,
        ),
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "failed"
    assert updated.failing_step == "opencode-connection"


def test_apply_opencode_verification_maps_non_zero_exit_to_process_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(
            extra_env={"IGNORED": "1"}
        ),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="boot failed\n",
            returncode=7,
        ),
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "failed"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-process-start"


def test_apply_opencode_verification_preserves_primary_failure_when_timeout_cleanup_also_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="partial output\n",
            timeout=True,
        ),
        stop_process=lambda launched_process: False,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_connection_status == "failed"
    assert updated.failing_step == "opencode-connection"


def test_apply_opencode_verification_maps_cleanup_failure_after_successful_handshake(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="local-lacc/recommended-6gb\n",
            returncode=0,
        ),
        stop_process=lambda launched_process: False,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "ready"
    assert updated.failing_step == "opencode-process-stop"


def test_apply_opencode_verification_passes_cleanup_timeout_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    captured: dict[str, object] = {}
    sentinel_now = object()
    sentinel_sleep = object()

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    def stop_process(process, *, now_fn, sleep_fn, timeout_seconds):
        captured["now_fn"] = now_fn
        captured["sleep_fn"] = sleep_fn
        captured["timeout_seconds"] = timeout_seconds
        return True

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="local-lacc/recommended-6gb\n",
            returncode=0,
        ),
        stop_process=stop_process,
        now_fn=sentinel_now,
        sleep_fn=sentinel_sleep,
    )

    assert updated.opencode_verification_status == "ready"
    assert captured["now_fn"] is sentinel_now
    assert captured["sleep_fn"] is sentinel_sleep
    assert captured["timeout_seconds"] == 5.0


def test_apply_opencode_verification_default_cleanup_receives_injected_clock_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    captured: dict[str, object] = {}
    sentinel_now = object()
    sentinel_sleep = object()

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    def default_stop_process(process, *, now_fn, sleep_fn, timeout_seconds):
        captured["now_fn"] = now_fn
        captured["sleep_fn"] = sleep_fn
        captured["timeout_seconds"] = timeout_seconds
        return True

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.stop_opencode_process",
        default_stop_process,
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="local-lacc/recommended-6gb\n",
            returncode=0,
        ),
        now_fn=sentinel_now,
        sleep_fn=sentinel_sleep,
    )

    assert updated.opencode_verification_status == "ready"
    assert captured["now_fn"] is sentinel_now
    assert captured["sleep_fn"] is sentinel_sleep
    assert captured["timeout_seconds"] == 5.0


def test_apply_opencode_verification_does_not_fallback_on_internal_typeerror_from_modern_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    def stop_process(process, *, now_fn, sleep_fn, timeout_seconds):
        calls.append("kwargs")
        raise TypeError("internal cleanup bug")

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="local-lacc/recommended-6gb\n",
            returncode=0,
        ),
        stop_process=stop_process,
    )

    assert calls == ["kwargs"]
    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "ready"
    assert updated.failing_step == "opencode-process-stop"
    assert "internal cleanup bug" in updated.error_message


def test_apply_opencode_verification_treats_terminate_race_as_successful_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    process = PollSequenceProcess(
        poll_values=[None, 0],
        stdout="local-lacc/recommended-6gb\n",
        returncode=0,
    )

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: process,
    )

    assert updated.opencode_verification_status == "ready"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "ready"
    assert updated.failing_step is None


def test_apply_opencode_verification_does_not_report_ready_process_when_output_collection_fails_with_unknown_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification._collect_process_output",
        lambda process, log_path, timeout_seconds: (_ for _ in ()).throw(
            OSError("log stream failed")
        ),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="ignored\n",
            returncode=None,
        ),
        stop_process=lambda launched_process: True,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status != "ready"
    assert updated.opencode_connection_status == "failed"
    assert updated.failing_step == "opencode-connection"
