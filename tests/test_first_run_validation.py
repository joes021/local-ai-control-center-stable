import json
from pathlib import Path

import pytest

from local_ai_control_center_installer import first_run_validation as frv
from local_ai_control_center_installer import opencode_verification as ov
from local_ai_control_center_installer.runtime_bootstrap import (
    _write_runtime_endpoint_config,
)
from local_ai_control_center_installer.session import InstallerSession


class FakeCompletedProcess:
    def __init__(self, stdout_text: str, *, returncode: int):
        self._stdout_text = stdout_text
        self.returncode = returncode
        self.communicate_timeouts: list[float] = []

    def communicate(self, timeout: float):
        self.communicate_timeouts.append(timeout)
        return self._stdout_text, None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None


def _write_active_model_config(path: Path, *, model_id: str = "recommended-6gb") -> Path:
    model_path = path.parent.parent / "models" / f"{model_id}.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("model", encoding="utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "model_id": model_id,
                "model_path": str(model_path),
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_managed_opencode_config(path: Path, *, base_url: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "autoupdate": False,
                "model": "local-lacc/recommended-6gb.gguf",
                "enabled_providers": ["local-lacc"],
                "provider": {
                    "local-lacc": {
                        "npm": "@ai-sdk/openai-compatible",
                        "options": {"baseURL": f"{base_url}/v1"},
                        "models": {
                            "recommended-6gb.gguf": {
                                "name": "recommended-6gb.gguf",
                                "limit": {
                                    "context": 262144,
                                    "output": 8192,
                                },
                            }
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _first_run_manifest() -> dict:
    return {
        "opencode_artifact": {
            "launch": {
                "executable_relative_path": "opencode.exe",
                "verification_args": ["--pure", "run", "--format", "json", "--model"],
                "extra_env": {"NO_COLOR": "1"},
            }
        }
    }


def _build_first_run_ready_session(
    tmp_path: Path,
    *,
    managed_port: int = 39281,
) -> InstallerSession:
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    opencode_root = install_root / "tools" / "opencode"
    config_root = install_root / "config"

    runtime_root.mkdir(parents=True, exist_ok=True)
    opencode_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "llama-server.exe").write_text("runtime", encoding="utf-8")
    (opencode_root / "opencode.exe").write_text("opencode", encoding="utf-8")

    active_model_config_path = _write_active_model_config(
        config_root / "active-model.json"
    )
    runtime_endpoint_config_path = _write_runtime_endpoint_config(
        config_root / "runtime-endpoint.json",
        port=managed_port,
    )
    managed_config_path = _write_managed_opencode_config(
        config_root / "opencode" / "managed-config.json",
        base_url=f"http://127.0.0.1:{managed_port}",
    )

    return InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        server_verification_status="ready",
        opencode_artifact_status="ready",
        opencode_verification_status="ready",
        install_opencode=True,
        install_root=str(install_root),
        runtime_artifact_path=str(runtime_root),
        active_model_config_path=str(active_model_config_path),
        runtime_endpoint_config_path=str(runtime_endpoint_config_path),
        opencode_artifact_path=str(opencode_root),
        opencode_config_path=str(managed_config_path),
    )


def test_apply_first_run_validation_marks_ready_after_real_opencode_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)
    captured: dict[str, object] = {}

    def fake_runtime_server_factory(target, **kwargs):
        captured["runtime_target"] = target
        return frv.TemporaryRuntimeHandle(
            process=object(),
            base_url=target.runtime_base_url,
            log_path=tmp_path / "runtime.log",
        )

    def fake_process_factory(command, *, cwd, env, log_path):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["log_path"] = log_path
        process = FakeCompletedProcess(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "READY",
                            }
                        }
                    ]
                }
            )
            + "\n",
            returncode=0,
        )
        captured["process"] = process
        return process

    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
        runtime_server_factory=fake_runtime_server_factory,
        process_factory=fake_process_factory,
        stop_process=lambda process: True,
        stop_runtime=lambda handle: True,
    )

    assert updated.first_run_status == "ready"
    assert updated.first_run_process_status == "ready"
    assert updated.first_run_connection_status == "ready"
    assert updated.failing_step is None
    assert updated.error_message is None
    assert updated.first_run_log_path is not None
    assert Path(updated.first_run_log_path).read_text(encoding="utf-8").strip().startswith("{")
    assert captured["command"][-1] == frv.FIRST_RUN_PROMPT
    assert captured["command"][-2] == "local-lacc/recommended-6gb.gguf"
    assert captured["process"].communicate_timeouts == [ov.OPENCODE_SMOKE_TIMEOUT_SECONDS]
    assert captured["env"]["OPENCODE_CONFIG"] == session.opencode_config_path
    embedded_config = json.loads(captured["env"]["OPENCODE_CONFIG_CONTENT"])
    assert embedded_config["model"] == "local-lacc/recommended-6gb.gguf"
    assert (
        embedded_config["provider"]["local-lacc"]["options"]["baseURL"]
        .endswith("/v1")
    )
    assert embedded_config["provider"]["local-lacc"]["models"] == {
        "recommended-6gb.gguf": {
            "name": "recommended-6gb.gguf",
            "limit": {
                "context": 262144,
                "output": 8192,
            },
        }
    }
    assert captured["env"]["OPENCODE_DISABLE_MODELS_FETCH"] == "true"
    assert captured["env"]["NO_COLOR"] == "1"


def test_apply_first_run_validation_fails_when_runtime_endpoint_config_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)
    session.runtime_endpoint_config_path = str(
        tmp_path / "install-root" / "config" / "missing-runtime-endpoint.json"
    )

    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
    )

    assert updated.first_run_status == "failed"
    assert updated.first_run_process_status == "skipped"
    assert updated.first_run_connection_status == "skipped"
    assert updated.failing_step == "first-run-prerequisites"


def test_apply_first_run_validation_fails_when_foreign_process_owns_managed_port(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)

    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
        port_is_free=lambda host, port: False,
        is_managed_runtime_port_owned_by_installation=(
            lambda port, runtime_executable, install_root: False
        ),
        process_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("foreign-owned managed port should not run OpenCode")
        ),
    )

    assert updated.first_run_status == "failed"
    assert updated.first_run_process_status == "skipped"
    assert updated.first_run_connection_status == "skipped"
    assert updated.failing_step == "first-run-runtime-server-start"
    assert "occupied by another process" in (updated.error_message or "").lower()


def test_apply_first_run_validation_reuses_same_owner_managed_runtime_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)
    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())
    monkeypatch.setattr(
        frv,
        "launch_llama_server",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("same-owner reuse should not start a new runtime")
        ),
    )

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
        port_is_free=lambda host, port: False,
        is_managed_runtime_port_owned_by_installation=(
            lambda port, runtime_executable, install_root: True
        ),
        process_factory=lambda *args, **kwargs: FakeCompletedProcess(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "READY",
                            }
                        }
                    ]
                }
            ),
            returncode=0,
        ),
        stop_process=lambda process: True,
    )

    assert updated.first_run_status == "ready"
    assert updated.first_run_process_status == "ready"
    assert updated.first_run_connection_status == "ready"


def test_apply_first_run_validation_restarts_same_owner_runtime_when_reuse_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)
    events: list[str] = []

    class FakeRuntimeProcess:
        def poll(self) -> int | None:
            return None

        def terminate(self) -> None:
            return None

        def kill(self) -> None:
            return None

    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())
    monkeypatch.setattr(
        frv,
        "launch_llama_server",
        lambda command, log_path: events.append("start-runtime") or FakeRuntimeProcess(),
    )
    monkeypatch.setattr(
        frv,
        "_probe_runtime_health_during_startup",
        lambda base_url, timeout_seconds=1.0: "ready",
    )

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
        port_is_free=lambda host, port: False,
        is_managed_runtime_port_owned_by_installation=(
            lambda port, runtime_executable, install_root: True
        ),
        stop_managed_runtime_on_port=lambda port, runtime_executable, install_root: (
            events.append("stop-owner") or True
        ),
        reuse_existing_managed_runtime=False,
        process_factory=lambda *args, **kwargs: FakeCompletedProcess(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "READY",
                            }
                        }
                    ]
                }
            ),
            returncode=0,
        ),
        stop_process=lambda process: True,
        stop_runtime=lambda handle: events.append("stop-runtime") or True,
        now_fn=lambda: 1.0,
        sleep_fn=lambda _: None,
    )

    assert updated.first_run_status == "ready"
    assert events == ["stop-owner", "start-runtime", "stop-runtime"]


def test_apply_first_run_validation_marks_process_failure_when_opencode_smoke_exits_non_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)
    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
        runtime_server_factory=lambda target, **kwargs: frv.TemporaryRuntimeHandle(
            process=object(),
            base_url=target.runtime_base_url,
            log_path=tmp_path / "runtime.log",
        ),
        process_factory=lambda *args, **kwargs: FakeCompletedProcess(
            '{"choices":[]}\n',
            returncode=7,
        ),
        stop_process=lambda process: True,
        stop_runtime=lambda handle: True,
    )

    assert updated.first_run_status == "failed"
    assert updated.first_run_process_status == "failed"
    assert updated.first_run_connection_status == "skipped"
    assert updated.failing_step == "first-run-opencode-smoke"


def test_apply_first_run_validation_fails_when_assistant_payload_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)
    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
        runtime_server_factory=lambda target, **kwargs: frv.TemporaryRuntimeHandle(
            process=object(),
            base_url=target.runtime_base_url,
            log_path=tmp_path / "runtime.log",
        ),
        process_factory=lambda *args, **kwargs: FakeCompletedProcess(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                            }
                        }
                    ]
                }
            ),
            returncode=0,
        ),
        stop_process=lambda process: True,
        stop_runtime=lambda handle: True,
    )

    assert updated.first_run_status == "failed"
    assert updated.first_run_process_status == "ready"
    assert updated.first_run_connection_status == "failed"
    assert updated.failing_step == "first-run-opencode-smoke"


def test_apply_first_run_validation_accepts_opencode_event_stream_text_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)
    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
        runtime_server_factory=lambda target, **kwargs: frv.TemporaryRuntimeHandle(
            process=object(),
            base_url=target.runtime_base_url,
            log_path=tmp_path / "runtime.log",
        ),
        process_factory=lambda *args, **kwargs: FakeCompletedProcess(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "step_start",
                            "part": {
                                "type": "step-start",
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "type": "text",
                            "part": {
                                "type": "text",
                                "text": "READY.",
                            },
                        }
                    ),
                ]
            )
            + "\n",
            returncode=0,
        ),
        stop_process=lambda process: True,
        stop_runtime=lambda handle: True,
    )

    assert updated.first_run_status == "ready"
    assert updated.first_run_process_status == "ready"
    assert updated.first_run_connection_status == "ready"
    assert updated.failing_step is None


def test_apply_first_run_validation_accepts_live_route_proof_when_stdout_has_only_step_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)
    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
        runtime_server_factory=lambda target, **kwargs: frv.TemporaryRuntimeHandle(
            process=object(),
            base_url=target.runtime_base_url,
            log_path=tmp_path / "runtime.log",
        ),
        relay_factory=lambda **kwargs: type(
            "RelayHandle",
            (),
            {
                "base_url": "http://127.0.0.1:9422",
                "proof_state": ov.RelayProofState(
                    marker_seen=True,
                    upstream_success=True,
                    response_has_assistant_content=True,
                ),
            },
        )(),
        process_factory=lambda *args, **kwargs: FakeCompletedProcess(
            json.dumps(
                {
                    "type": "step_start",
                    "part": {
                        "type": "step-start",
                    },
                }
            )
            + "\n",
            returncode=0,
        ),
        stop_process=lambda process: True,
        stop_relay=lambda handle: True,
        stop_runtime=lambda handle: True,
    )

    assert updated.first_run_status == "ready"
    assert updated.first_run_process_status == "ready"
    assert updated.first_run_connection_status == "ready"
    assert updated.failing_step is None


def test_apply_first_run_validation_maps_cleanup_failure_after_success_to_process_stop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    session = _build_first_run_ready_session(tmp_path)
    monkeypatch.setattr(frv, "load_opencode_manifest", lambda: _first_run_manifest())

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
        runtime_server_factory=lambda target, **kwargs: frv.TemporaryRuntimeHandle(
            process=object(),
            base_url=target.runtime_base_url,
            log_path=tmp_path / "runtime.log",
        ),
        process_factory=lambda *args, **kwargs: FakeCompletedProcess(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "READY",
                            }
                        }
                    ]
                }
            ),
            returncode=0,
        ),
        stop_process=lambda process: False,
        stop_runtime=lambda handle: True,
    )

    assert updated.first_run_status == "failed"
    assert updated.first_run_process_status == "ready"
    assert updated.first_run_connection_status == "ready"
    assert updated.failing_step == "first-run-process-stop"


def test_apply_first_run_validation_skips_when_opencode_is_not_requested(
    tmp_path: Path,
):
    session = InstallerSession(
        install_opencode=False,
        bootstrap_status="ready",
        runtime_payload_status="ready",
        server_verification_status="ready",
        opencode_artifact_status="skipped",
        opencode_verification_status="skipped",
    )

    updated = frv.apply_first_run_validation(
        session,
        temp_root=tmp_path / "temp-runs",
    )

    assert updated.first_run_status == "skipped"
    assert updated.first_run_process_status == "skipped"
    assert updated.first_run_connection_status == "skipped"


def test_launch_first_run_process_detaches_child_from_parent_stdin(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(frv.subprocess, "Popen", fake_popen)

    result = frv.launch_first_run_process(
        ["opencode.exe", "--pure"],
        cwd=tmp_path,
        env={"EXAMPLE": "1"},
        log_path=tmp_path / "ignored.log",
    )

    assert result is sentinel
    assert captured["stdin"] is frv.subprocess.DEVNULL
    assert captured["stdout"] is frv.subprocess.PIPE
    assert captured["stderr"] is frv.subprocess.STDOUT
    assert captured["text"] is True
