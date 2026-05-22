import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from subprocess import TimeoutExpired
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from local_ai_control_center_installer import opencode_verification as ov
from local_ai_control_center_installer.session import InstallerSession


def _build_manifest(
    *,
    extra_env: dict[str, str] | None = None,
    executable_relative_path: str = "opencode.exe",
    verification_args: list[str] | None = None,
) -> dict:
    return {
        "opencode_artifact": {
            "id": "windows-opencode",
            "launch": {
                "executable_relative_path": executable_relative_path,
                "verification_args": verification_args
                or ["--pure", "run", "--format", "json", "--model"],
                "extra_env": extra_env or {},
            },
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
    runtime_root = install_root / "tools" / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "llama-server.exe").write_text("binary", encoding="utf-8")
    opencode_root = install_root / "tools" / "opencode"
    opencode_root.mkdir(parents=True, exist_ok=True)
    (opencode_root / "opencode.exe").write_text("binary", encoding="utf-8")
    managed_config_path = _write_managed_config(
        install_root / "config" / "opencode" / "managed-config.json",
        verified_server_url="http://127.0.0.1:8080",
    )
    return InstallerSession(
        started_at="2026-05-22T10:11:12",
        runtime_artifact_status="ready",
        opencode_artifact_status="ready",
        opencode_verification_status="failed",
        opencode_process_status="failed",
        opencode_connection_status="failed",
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(active_model_config_path),
        runtime_artifact_path=str(runtime_root),
        opencode_artifact_path=str(opencode_root),
        opencode_config_path=str(managed_config_path),
        failing_step="earlier-step",
        error_message="earlier error",
    )


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

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = 0


class NeverHealthyRuntimeProcess(FakeProcess):
    def __init__(self) -> None:
        super().__init__(stdout="", returncode=None)

    def poll(self):
        return None


def _proof_state(
    *,
    marker_seen: bool = False,
    upstream_success: bool = False,
    response_has_assistant_content: bool = False,
    upstream_error: str | None = None,
):
    return SimpleNamespace(
        marker_seen=marker_seen,
        upstream_success=upstream_success,
        response_has_assistant_content=response_has_assistant_content,
        upstream_error=upstream_error,
    )


def _runtime_handle(tmp_path: Path, *, base_url: str = "http://127.0.0.1:9101"):
    return SimpleNamespace(
        process=FakeProcess(),
        base_url=base_url,
        log_path=tmp_path / "runtime.log",
    )


def _relay_handle(
    *,
    base_url: str = "http://127.0.0.1:9202",
    proof_state=None,
):
    return SimpleNamespace(
        server=object(),
        base_url=base_url,
        proof_state=proof_state or _proof_state(),
    )


def test_apply_opencode_verification_skips_when_artifact_not_ready(tmp_path: Path):
    session = InstallerSession(
        opencode_artifact_status="failed",
        opencode_verification_status="failed",
        opencode_process_status="failed",
        opencode_connection_status="failed",
        failing_step="opencode-artifact",
        error_message="artifact missing",
    )

    updated = ov.apply_opencode_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.opencode_verification_status == "skipped"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-artifact"
    assert updated.error_message == "artifact missing"


def test_apply_opencode_verification_success_path_uses_bounded_smoke_and_relay_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    marker = "LACC_VERIFY_MARKER:demo-token"
    runtime_handle = _runtime_handle(tmp_path, base_url="http://127.0.0.1:9311")
    proof_state = _proof_state(
        marker_seen=True,
        upstream_success=True,
        response_has_assistant_content=True,
    )
    relay_handle = _relay_handle(
        base_url="http://127.0.0.1:9422",
        proof_state=proof_state,
    )
    process = FakeProcess(stdout='{"ok":true}\n', returncode=0)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(
            extra_env={
                "CUSTOM_FLAG": "enabled",
                "OPENCODE_DISABLE_MODELS_FETCH": "false",
            }
        ),
    )

    def runtime_server_factory(target, *, run_paths, now_fn, sleep_fn):
        captured["runtime_target"] = target
        captured["runtime_log_path"] = run_paths.server_log_path
        return runtime_handle

    def relay_factory(*, upstream_base_url, marker, now_fn, sleep_fn):
        captured["relay_upstream_base_url"] = upstream_base_url
        captured["relay_marker"] = marker
        return relay_handle

    def process_factory(command, *, cwd, env, log_path):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        captured["log_path"] = log_path
        return process

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=process_factory,
        runtime_server_factory=runtime_server_factory,
        relay_factory=relay_factory,
        stop_process=lambda launched_process: True,
        stop_runtime=lambda handle: True,
        stop_relay=lambda handle: True,
        marker_factory=lambda: marker,
    )

    assert updated.opencode_verification_status == "ready"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "ready"
    assert updated.failing_step is None
    assert updated.error_message is None
    assert updated.verified_opencode_command == (
        f"{Path(session.opencode_artifact_path) / 'opencode.exe'} "
        "--pure run --format json --model "
        "local-lacc/recommended-6gb "
        f"Repeat this exact token once: {marker}"
    )
    assert captured["command"] == [
        str(Path(session.opencode_artifact_path) / "opencode.exe"),
        "--pure",
        "run",
        "--format",
        "json",
        "--model",
        "local-lacc/recommended-6gb",
        f"Repeat this exact token once: {marker}",
    ]
    assert captured["relay_upstream_base_url"] == runtime_handle.base_url
    assert captured["relay_marker"] == marker
    assert captured["log_path"] == Path(updated.opencode_log_path)
    assert Path(updated.opencode_log_path).read_text(encoding="utf-8") == '{"ok":true}\n'
    assert list(Path(captured["cwd"]).iterdir()) == []
    env = captured["env"]
    assert env["CUSTOM_FLAG"] == "enabled"
    assert env["OPENCODE_CONFIG"] == session.opencode_config_path
    assert env["OPENCODE_DISABLE_MODELS_FETCH"] == "true"
    embedded_config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    assert embedded_config["model"] == "local-lacc/recommended-6gb"
    assert (
        embedded_config["providers"]["local-lacc"]["options"]["baseURL"]
        == "http://127.0.0.1:9422/v1"
    )
    persisted_config = json.loads(
        Path(session.opencode_config_path).read_text(encoding="utf-8")
    )
    assert (
        persisted_config["providers"]["local-lacc"]["options"]["baseURL"]
        == "http://127.0.0.1:8080/v1"
    )


def test_apply_opencode_verification_runtime_start_failure_skips_process_and_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    process_called = False

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    def process_factory(command, *, cwd, env, log_path):
        nonlocal process_called
        process_called = True
        return FakeProcess()

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=process_factory,
        runtime_server_factory=lambda target, *, run_paths, now_fn, sleep_fn: (_ for _ in ()).throw(
            OSError("runtime launch failed")
        ),
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-runtime-server-start"
    assert updated.error_message == "runtime launch failed"
    assert process_called is False


def test_apply_opencode_verification_runtime_never_becomes_healthy_maps_to_runtime_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    runtime_process = NeverHealthyRuntimeProcess()
    process_called = False
    clock = {"now": 0.0}

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )
    monkeypatch.setattr(
        ov,
        "choose_free_port",
        lambda host="127.0.0.1": 9544,
    )
    monkeypatch.setattr(
        ov,
        "_launch_temporary_runtime_process",
        lambda command, log_path: runtime_process,
    )
    monkeypatch.setattr(
        ov,
        "_probe_runtime_health_during_startup",
        lambda base_url, timeout_seconds=1.0: "loading",
    )

    def now_fn():
        return clock["now"]

    def sleep_fn(seconds):
        clock["now"] += seconds

    def process_factory(command, *, cwd, env, log_path):
        nonlocal process_called
        process_called = True
        return FakeProcess()

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=process_factory,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-runtime-server-start"
    assert "healthy" in updated.error_message
    assert process_called is False


def test_apply_opencode_verification_relay_start_failure_skips_process_and_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    process_called = False
    runtime_handle = _runtime_handle(tmp_path)
    cleaned_runtime: list[object] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    def process_factory(command, *, cwd, env, log_path):
        nonlocal process_called
        process_called = True
        return FakeProcess()

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=process_factory,
        runtime_server_factory=lambda target, *, run_paths, now_fn, sleep_fn: runtime_handle,
        relay_factory=lambda **kwargs: (_ for _ in ()).throw(OSError("relay bind failed")),
        stop_runtime=lambda handle: cleaned_runtime.append(handle) or True,
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-relay-start"
    assert updated.error_message == "relay bind failed"
    assert process_called is False
    assert cleaned_runtime == [runtime_handle]


def test_apply_opencode_verification_process_failure_before_any_proof_skips_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="smoke failed\n",
            returncode=7,
        ),
        runtime_server_factory=lambda target, *, run_paths, now_fn, sleep_fn: _runtime_handle(
            tmp_path
        ),
        relay_factory=lambda **kwargs: _relay_handle(proof_state=_proof_state()),
        stop_process=lambda launched_process: True,
        stop_runtime=lambda handle: True,
        stop_relay=lambda handle: True,
        marker_factory=lambda: "LACC_VERIFY_MARKER:red",
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "failed"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-inference-smoke"


def test_apply_opencode_verification_relay_without_marker_fails_live_route_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout='{"ok":true}\n',
            returncode=0,
        ),
        runtime_server_factory=lambda target, *, run_paths, now_fn, sleep_fn: _runtime_handle(
            tmp_path
        ),
        relay_factory=lambda **kwargs: _relay_handle(proof_state=_proof_state()),
        stop_process=lambda launched_process: True,
        stop_runtime=lambda handle: True,
        stop_relay=lambda handle: True,
        marker_factory=lambda: "LACC_VERIFY_MARKER:no-hit",
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "failed"
    assert updated.failing_step == "opencode-live-route-proof"


def test_apply_opencode_verification_preserves_partial_proof_when_process_fails_after_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    proof_state = _proof_state(
        marker_seen=True,
        upstream_success=True,
        response_has_assistant_content=True,
    )

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="partial success\n",
            returncode=9,
        ),
        runtime_server_factory=lambda target, *, run_paths, now_fn, sleep_fn: _runtime_handle(
            tmp_path
        ),
        relay_factory=lambda **kwargs: _relay_handle(proof_state=proof_state),
        stop_process=lambda launched_process: True,
        stop_runtime=lambda handle: True,
        stop_relay=lambda handle: True,
        marker_factory=lambda: "LACC_VERIFY_MARKER:partial",
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "failed"
    assert updated.opencode_connection_status == "ready"
    assert updated.failing_step == "opencode-inference-smoke"


def test_apply_opencode_verification_upstream_proof_failure_wins_over_process_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    proof_state = _proof_state(
        marker_seen=True,
        upstream_success=False,
        response_has_assistant_content=False,
        upstream_error="upstream returned invalid assistant payload",
    )

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="bad relay proof\n",
            returncode=4,
        ),
        runtime_server_factory=lambda target, *, run_paths, now_fn, sleep_fn: _runtime_handle(
            tmp_path
        ),
        relay_factory=lambda **kwargs: _relay_handle(proof_state=proof_state),
        stop_process=lambda launched_process: True,
        stop_runtime=lambda handle: True,
        stop_relay=lambda handle: True,
        marker_factory=lambda: "LACC_VERIFY_MARKER:upstream",
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "failed"
    assert updated.opencode_connection_status == "failed"
    assert updated.failing_step == "opencode-live-route-proof"
    assert "invalid assistant payload" in updated.error_message


def test_apply_opencode_verification_cleanup_failure_after_successful_proof_maps_to_process_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    proof_state = _proof_state(
        marker_seen=True,
        upstream_success=True,
        response_has_assistant_content=True,
    )

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout='{"ok":true}\n',
            returncode=0,
        ),
        runtime_server_factory=lambda target, *, run_paths, now_fn, sleep_fn: _runtime_handle(
            tmp_path
        ),
        relay_factory=lambda **kwargs: _relay_handle(proof_state=proof_state),
        stop_process=lambda launched_process: False,
        stop_runtime=lambda handle: True,
        stop_relay=lambda handle: True,
        marker_factory=lambda: "LACC_VERIFY_MARKER:cleanup",
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "ready"
    assert updated.failing_step == "opencode-process-stop"


def test_apply_opencode_verification_cleanup_failure_does_not_overwrite_primary_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(),
    )

    updated = ov.apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, *, cwd, env, log_path: FakeProcess(
            stdout="smoke failed\n",
            returncode=6,
        ),
        runtime_server_factory=lambda target, *, run_paths, now_fn, sleep_fn: _runtime_handle(
            tmp_path
        ),
        relay_factory=lambda **kwargs: _relay_handle(proof_state=_proof_state()),
        stop_process=lambda launched_process: False,
        stop_runtime=lambda handle: True,
        stop_relay=lambda handle: True,
        marker_factory=lambda: "LACC_VERIFY_MARKER:cleanup-loss",
    )

    assert updated.opencode_verification_status == "failed"
    assert updated.opencode_process_status == "failed"
    assert updated.opencode_connection_status == "skipped"
    assert updated.failing_step == "opencode-inference-smoke"
    assert "failed to stop OpenCode verification process" in updated.error_message


def _start_loopback_server(handler_type: type[BaseHTTPRequestHandler]):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_type)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}", thread


def _stop_loopback_server(server: ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()


def _post_json(url: str, payload: dict, *, content_type: str = "application/json"):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": content_type},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return response.status, response.read().decode("utf-8")


def test_verification_relay_loopback_rejects_invalid_routes_methods_and_non_json_and_extracts_marker():
    marker = "LACC_VERIFY_MARKER:relay-proof"
    upstream_requests: list[dict[str, object]] = []

    class UpstreamHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            upstream_requests.append(
                {
                    "path": self.path,
                    "body": json.loads(body),
                }
            )
            response_bytes = json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": f"confirmed {marker}",
                            }
                        }
                    ]
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_bytes)))
            self.end_headers()
            self.wfile.write(response_bytes)

        def log_message(self, format, *args):
            return

    upstream_server, upstream_base_url, upstream_thread = _start_loopback_server(
        UpstreamHandler
    )
    relay_handle = None

    try:
        proof_state = ov.RelayProofState()
        relay_handle = ov.start_verification_relay(
            upstream_base_url=upstream_base_url,
            marker=marker,
            proof_state=proof_state,
        )

        with pytest.raises(HTTPError) as wrong_path_error:
            _post_json(
                f"{relay_handle.base_url}/v1/not-chat",
                {"messages": [{"role": "user", "content": marker}]},
            )
        assert wrong_path_error.value.code == 404

        with pytest.raises(HTTPError) as wrong_method_error:
            urlopen(f"{relay_handle.base_url}/v1/chat/completions", timeout=5)
        assert wrong_method_error.value.code == 405

        request = Request(
            f"{relay_handle.base_url}/v1/chat/completions",
            data=b"plain text is not json",
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        with pytest.raises(HTTPError) as wrong_type_error:
            urlopen(request, timeout=5)
        assert wrong_type_error.value.code == 415

        status, response_text = _post_json(
            f"{relay_handle.base_url}/v1/chat/completions",
            {
                "messages": [
                    {
                        "role": "system",
                        "content": "irrelevant",
                    },
                    {
                        "role": "user",
                        "content": f"Repeat this exact token once: {marker}",
                    },
                ]
            },
        )

        assert status == 200
        assert marker in response_text
        assert proof_state.marker_seen is True
        assert proof_state.upstream_success is True
        assert proof_state.response_has_assistant_content is True
        assert proof_state.upstream_error is None
        assert upstream_requests == [
            {
                "path": "/v1/chat/completions",
                "body": {
                    "messages": [
                        {"role": "system", "content": "irrelevant"},
                        {
                            "role": "user",
                            "content": f"Repeat this exact token once: {marker}",
                        },
                    ]
                },
            }
        ]
    finally:
        if relay_handle is not None:
            ov.stop_verification_relay(relay_handle)
        _stop_loopback_server(upstream_server, upstream_thread)


@pytest.mark.parametrize(
    ("response_bytes", "content_type", "expected_error"),
    [
        (b"{invalid json", "application/json", "upstream returned invalid JSON"),
        (
            json.dumps(
                {
                    "choices": [
                        {"message": {"role": "assistant"}},
                    ]
                }
            ).encode("utf-8"),
            "application/json",
            "upstream returned invalid assistant payload",
        ),
        (
            json.dumps(
                {
                    "choices": [
                        {"message": {"content": "assistant-looking text without role"}},
                    ]
                }
            ).encode("utf-8"),
            "application/json",
            "upstream returned invalid assistant payload",
        ),
    ],
)
def test_verification_relay_marks_upstream_success_false_for_invalid_or_empty_assistant_payload(
    response_bytes: bytes,
    content_type: str,
    expected_error: str,
):
    marker = "LACC_VERIFY_MARKER:upstream-check"

    class UpstreamHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(response_bytes)))
            self.end_headers()
            self.wfile.write(response_bytes)

        def log_message(self, format, *args):
            return

    upstream_server, upstream_base_url, upstream_thread = _start_loopback_server(
        UpstreamHandler
    )
    relay_handle = None

    try:
        proof_state = ov.RelayProofState()
        relay_handle = ov.start_verification_relay(
            upstream_base_url=upstream_base_url,
            marker=marker,
            proof_state=proof_state,
        )

        status, _ = _post_json(
            f"{relay_handle.base_url}/v1/chat/completions",
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Repeat this exact token once: {marker}",
                    }
                ]
            },
        )

        assert status == 200
        assert proof_state.marker_seen is True
        assert proof_state.upstream_success is False
        assert proof_state.response_has_assistant_content is False
        assert proof_state.upstream_error == expected_error
    finally:
        if relay_handle is not None:
            ov.stop_verification_relay(relay_handle)
        _stop_loopback_server(upstream_server, upstream_thread)
