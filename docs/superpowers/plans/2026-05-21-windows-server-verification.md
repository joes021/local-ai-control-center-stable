# Windows Server Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next Windows installer slice for `Local AI Control Center`: verify that the pinned `llama.cpp` server can start against the active model, answer health, stop cleanly, and report truthful runnable-server status without yet claiming a complete product install.

**Architecture:** Keep durable server-verification behavior inside the Python installer core. Add a focused `server_verification.py` module after runtime payload preparation, use injected collaborators for process startup, HTTP health probing, and cleanup so tests stay deterministic, and preserve the existing “truthful status first” pattern across session state, reporting, and CLI exit gates.

**Tech Stack:** Python 3.11+, `pytest`, standard-library `dataclasses`, `json`, `pathlib`, `subprocess`, `socket`, `time`, `urllib.request`, `urllib.error`, and `tempfile`

---

## File Map

- Modify: `README.md`
  - update slice status after runnable-server verification lands
- Modify: `src/local_ai_control_center_installer/session.py`
  - add server-verification state, verified URL/port, and server log path
- Modify: `src/local_ai_control_center_installer/reporting.py`
  - add server-verification fields to temp-run and install-root reports
- Modify: `src/local_ai_control_center_installer/defaults.py`
  - wire the real default server-verification phase after runtime payload
- Modify: `src/local_ai_control_center_installer/main.py`
  - add server-verification collaborator and tighten CLI exit truth
- Create: `src/local_ai_control_center_installer/server_verification.py`
  - prerequisite resolution, port selection, process launch, health polling, cleanup, and server-verification truth table
- Modify: `tests/test_session.py`
  - cover server-verification fields in session serialization
- Modify: `tests/test_reporting.py`
  - cover server-verification lines and JSON fields in reports
- Modify: `tests/test_main.py`
  - cover orchestration ordering and CLI exit behavior for server verification
- Modify: `tests/test_package_smoke.py`
  - keep the injected-collaborator smoke test aligned with the new server-verification step
- Create: `tests/test_server_verification.py`
  - cover skip semantics, prerequisite failures, success path, `503` loading behavior, failure-step priority, and cleanup truth

## Implementation Notes

- Use TDD throughout. Every new behavior starts with a failing test, then the minimal implementation, then the smallest safe refactor.
- Keep this slice narrow. Do not add `OpenCode`, inference prompts, portal lifecycle controls, or generic service-manager abstractions.
- Use only loopback verification for this slice:
  - base URL shape: `http://127.0.0.1:<port>`
  - health endpoint: `GET /health`
  - ready response: HTTP `200` with JSON body containing `{"status": "ok"}`
  - transitional loading response: HTTP `503` with JSON error payload indicating model loading; continue polling in this case until timeout
- Do not run a real `llama-server` process in unit tests. Use injected process factory, health probe, stop function, clock, and sleep collaborators.
- Keep failure-step priority aligned with the approved spec:
  - earliest verification failure wins
  - cleanup failure overwrites `failing_step` only if all earlier gates passed
  - cleanup failure after an earlier verification failure belongs in diagnostics, not as the primary failure step
- The default implementation may use a simple installer-owned free-port helper backed by `socket`.
- The server verification log should live in the temp run directory as `llama-server.log`; reports may reference that path directly rather than copying the server log into install-root artifacts in this slice.
- `product_installation_status` must remain `incomplete`.

### Task 1: Extend Session And Reporting For Server Verification Truth

**Files:**
- Modify: `src/local_ai_control_center_installer/session.py`
- Modify: `src/local_ai_control_center_installer/reporting.py`
- Modify: `tests/test_session.py`
- Modify: `tests/test_reporting.py`

- [ ] **Step 1: Write the failing session and reporting tests**

```python
from local_ai_control_center_installer.session import InstallerSession


def test_installer_session_serializes_server_verification_fields():
    session = InstallerSession(
        server_verification_status="ready",
        server_process_status="ready",
        server_health_status="ready",
        verified_server_port=8080,
        verified_server_url="http://127.0.0.1:8080",
        server_log_path="C:\\LACC\\temp\\llama-server.log",
    )

    payload = session.to_dict()

    assert payload["server_verification_status"] == "ready"
    assert payload["server_process_status"] == "ready"
    assert payload["server_health_status"] == "ready"
    assert payload["verified_server_port"] == 8080
    assert payload["verified_server_url"] == "http://127.0.0.1:8080"
    assert payload["server_log_path"].endswith("llama-server.log")
```

```python
from pathlib import Path

from local_ai_control_center_installer.reporting import (
    build_run_paths,
    write_human_log,
    write_json_report,
)
from local_ai_control_center_installer.session import InstallerSession


def test_build_run_paths_exposes_server_log_path(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    assert paths.server_log_path == (
        tmp_path
        / "LocalAIControlCenterInstaller"
        / "runs"
        / "2026-05-21T10-00-00"
        / "llama-server.log"
    )


def test_write_json_report_serializes_server_verification_summary(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        server_verification_status="failed",
        server_process_status="ready",
        server_health_status="failed",
        verified_server_port=8080,
        verified_server_url="http://127.0.0.1:8080",
        server_log_path=str(paths.server_log_path),
        failing_step="server-health",
        install_root=str(tmp_path / "install-root"),
    )

    write_json_report(session, paths.json_report_path)

    payload = json.loads(paths.json_report_path.read_text(encoding="utf-8"))
    assert payload["server_verification_status"] == "failed"
    assert payload["server_process_status"] == "ready"
    assert payload["server_health_status"] == "failed"
    assert payload["verified_server_port"] == 8080
    assert payload["verified_server_url"] == "http://127.0.0.1:8080"
    assert payload["server_log_path"].endswith("llama-server.log")


def test_write_human_log_includes_server_verification_lines(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    session = InstallerSession(
        install_root=str(tmp_path / "install-root"),
        server_verification_status="failed",
        server_process_status="ready",
        server_health_status="failed",
        verified_server_port=8080,
        verified_server_url="http://127.0.0.1:8080",
        server_log_path=str(paths.server_log_path),
        failing_step="server-health",
    )

    write_human_log(session, paths.log_path)

    contents = paths.log_path.read_text(encoding="utf-8")
    assert "Server verification status: failed" in contents
    assert "Server process status: ready" in contents
    assert "Server health status: failed" in contents
    assert "Verified server port: 8080" in contents
    assert "Verified server URL: http://127.0.0.1:8080" in contents
    assert "Server log path:" in contents
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_session.py::test_installer_session_serializes_server_verification_fields tests/test_reporting.py::test_build_run_paths_exposes_server_log_path tests/test_reporting.py::test_write_json_report_serializes_server_verification_summary tests/test_reporting.py::test_write_human_log_includes_server_verification_lines -v`
Expected: FAIL because the session and report structures do not yet define server-verification fields

- [ ] **Step 3: Add the minimal session and reporting fields**

Extend `InstallerSession` with conservative defaults:

```python
server_verification_status: str = "skipped"
server_process_status: str = "skipped"
server_health_status: str = "skipped"
verified_server_port: int | None = None
verified_server_url: str | None = None
server_log_path: str | None = None
```

Extend `RunPaths` in `reporting.py`:

```python
@dataclass
class RunPaths:
    run_dir: Path
    log_path: Path
    json_report_path: Path
    server_log_path: Path
```

Update `build_run_paths()` so `server_log_path` is:

```python
server_log_path=run_dir / "llama-server.log"
```

Update `write_human_log()` to include:

- `Server verification status`
- `Server process status`
- `Server health status`
- `Verified server port`
- `Verified server URL`
- `Server log path`

Update `write_json_report()` to include:

- `server_verification_status`
- `server_process_status`
- `server_health_status`
- `verified_server_port`
- `verified_server_url`
- `server_log_path`

- [ ] **Step 4: Run the targeted tests again**

Run: `python -m pytest tests/test_session.py::test_installer_session_serializes_server_verification_fields tests/test_reporting.py::test_build_run_paths_exposes_server_log_path tests/test_reporting.py::test_write_json_report_serializes_server_verification_summary tests/test_reporting.py::test_write_human_log_includes_server_verification_lines -v`
Expected: PASS

- [ ] **Step 5: Run the full session and reporting test files**

Run: `python -m pytest tests/test_session.py tests/test_reporting.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_ai_control_center_installer/session.py src/local_ai_control_center_installer/reporting.py tests/test_session.py tests/test_reporting.py
git commit -m "feat: add server verification session and reporting state"
```

### Task 2: Create Server Verification Prerequisite Resolution And Skip Rules

**Files:**
- Create: `src/local_ai_control_center_installer/server_verification.py`
- Create: `tests/test_server_verification.py`

- [ ] **Step 1: Write the failing skip and prerequisite tests**

```python
import json
from pathlib import Path

from local_ai_control_center_installer.server_verification import apply_server_verification
from local_ai_control_center_installer.session import InstallerSession


def test_apply_server_verification_skips_when_runtime_payload_is_not_ready(tmp_path: Path):
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="failed",
        install_root=str(tmp_path / "install-root"),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "skipped"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"


def test_apply_server_verification_fails_when_active_model_config_is_missing(tmp_path: Path):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        install_root=str(install_root),
        active_model_config_path=str(install_root / "config" / "active-model.json"),
        runtime_artifact_path=str(runtime_root),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"


def test_apply_server_verification_fails_when_llama_server_exe_is_missing(tmp_path: Path):
    install_root = tmp_path / "install-root"
    config_root = install_root / "config"
    model_path = install_root / "models" / "starter.gguf"
    config_root.mkdir(parents=True)
    model_path.parent.mkdir(parents=True)
    model_path.write_text("ok", encoding="utf-8")
    (config_root / "active-model.json").write_text(
        json.dumps({"model_id": "recommended-6gb", "model_path": str(model_path)}),
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        install_root=str(install_root),
        active_model_config_path=str(config_root / "active-model.json"),
        runtime_artifact_path=str(install_root / "runtime" / "llama.cpp"),
    )

    updated = apply_server_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "skipped"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-verification-prerequisites"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_server_verification.py::test_apply_server_verification_skips_when_runtime_payload_is_not_ready tests/test_server_verification.py::test_apply_server_verification_fails_when_active_model_config_is_missing tests/test_server_verification.py::test_apply_server_verification_fails_when_llama_server_exe_is_missing -v`
Expected: FAIL with `ImportError` because `server_verification.py` does not exist yet

- [ ] **Step 3: Implement the minimal verification skeleton**

Start `server_verification.py` with:

```python
import json
from dataclasses import dataclass
from pathlib import Path

from local_ai_control_center_installer.reporting import build_run_paths
from local_ai_control_center_installer.session import InstallerSession


@dataclass
class ServerVerificationTarget:
    server_executable: Path
    model_id: str
    model_path: Path
    active_model_config_path: Path


def apply_server_verification(
    session: InstallerSession,
    *,
    temp_root: Path,
    process_factory=None,
    health_probe=None,
    stop_process=None,
    select_port=None,
    now_fn=None,
    sleep_fn=None,
) -> InstallerSession:
    if (
        session.bootstrap_status != "ready"
        or session.runtime_payload_status != "ready"
    ):
        session.server_verification_status = "skipped"
        session.server_process_status = "skipped"
        session.server_health_status = "skipped"
        return session

    run_id = (session.started_at or "manual-run").replace(":", "-")
    run_paths = build_run_paths(temp_root, run_id)
    session.server_log_path = str(run_paths.server_log_path)

    try:
        target = resolve_server_verification_target(session)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        session.server_verification_status = "failed"
        session.server_process_status = "skipped"
        session.server_health_status = "skipped"
        session.failing_step = "server-verification-prerequisites"
        session.error_message = str(exc)
        return session

    ...
```

Add `resolve_server_verification_target(session)` that:

- requires `session.active_model_config_path`
- reads `active-model.json`
- validates non-empty string `model_id` and `model_path`
- requires the model file to exist
- resolves `llama-server.exe` from `session.runtime_artifact_path`

Leave process launch unimplemented for now by returning the session after target resolution with statuses still unset, so the prerequisite tests can pass before the success path is added.

- [ ] **Step 4: Run the prerequisite tests again**

Run: `python -m pytest tests/test_server_verification.py::test_apply_server_verification_skips_when_runtime_payload_is_not_ready tests/test_server_verification.py::test_apply_server_verification_fails_when_active_model_config_is_missing tests/test_server_verification.py::test_apply_server_verification_fails_when_llama_server_exe_is_missing -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/server_verification.py tests/test_server_verification.py
git commit -m "feat: add server verification prerequisite handling"
```

### Task 3: Implement Process Start, `503` Polling, And Ready Success Path

**Files:**
- Modify: `src/local_ai_control_center_installer/server_verification.py`
- Modify: `tests/test_server_verification.py`

- [ ] **Step 1: Write the failing success-path and startup tests**

Add to `tests/test_server_verification.py`:

```python
class FakeProcess:
    def __init__(self, poll_results: list[int | None]):
        self._poll_results = iter(poll_results)
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self):
        try:
            return next(self._poll_results)
        except StopIteration:
            return None

    def terminate(self):
        self.terminate_calls += 1

    def kill(self):
        self.kill_calls += 1
```

```python
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
        now_fn=_fake_now([0.0]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "failed"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-process-start"
```

Add test helpers:

```python
def _fake_now(values: list[float]):
    iterator = iter(values)
    last = values[-1]

    def _now():
        nonlocal last
        try:
            last = next(iterator)
        except StopIteration:
            pass
        return last

    return _now
```

```python
def _build_runtime_ready_session(tmp_path: Path) -> InstallerSession:
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    config_root = install_root / "config"
    model_path = install_root / "models" / "starter.gguf"
    runtime_root.mkdir(parents=True)
    config_root.mkdir(parents=True)
    model_path.parent.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    model_path.write_text("ok", encoding="utf-8")
    active_model_path = config_root / "active-model.json"
    active_model_path.write_text(
        json.dumps({"model_id": "recommended-6gb", "model_path": str(model_path)}),
        encoding="utf-8",
    )
    return InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        install_root=str(install_root),
        active_model_config_path=str(active_model_path),
        runtime_artifact_path=str(runtime_root),
    )
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_server_verification.py::test_apply_server_verification_marks_ready_after_healthy_start_and_clean_stop tests/test_server_verification.py::test_apply_server_verification_continues_polling_through_loading_503_until_ready tests/test_server_verification.py::test_apply_server_verification_marks_process_start_failure_when_process_exits_early tests/test_server_verification.py::test_apply_server_verification_maps_subprocess_start_exception_to_server_process_start -v`
Expected: FAIL because process startup, health polling, and ready-state truth are not implemented yet

- [ ] **Step 3: Implement the minimal success path**

Add narrow helpers to `server_verification.py`:

```python
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
```

```python
def choose_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])
```

```python
def launch_llama_server(command: list[str], log_path: Path) -> subprocess.Popen[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        command,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
```

```python
def probe_server_health(base_url: str) -> str:
    try:
        with urlopen(f"{base_url}/health") as response:
            payload = json.loads(response.read().decode("utf-8"))
            if response.status == 200 and payload.get("status") == "ok":
                return "ready"
    except HTTPError as exc:
        if exc.code == 503:
            return "loading"
        return "failed"
    except (URLError, json.JSONDecodeError, OSError):
        return "failed"
    return "failed"
```

Complete `apply_server_verification()` so it:

- selects a port
- records `verified_server_port` and `verified_server_url`
- launches a process
- maps `process_factory` exceptions to `server-process-start`
- waits through a bounded startup window for the process to remain alive
- polls health until `ready`, `failed`, or timeout
- on success:
  - `server_process_status = "ready"`
  - `server_health_status = "ready"`
  - `server_verification_status = "ready"`

- [ ] **Step 4: Run the targeted tests again**

Run: `python -m pytest tests/test_server_verification.py::test_apply_server_verification_marks_ready_after_healthy_start_and_clean_stop tests/test_server_verification.py::test_apply_server_verification_continues_polling_through_loading_503_until_ready tests/test_server_verification.py::test_apply_server_verification_marks_process_start_failure_when_process_exits_early -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/server_verification.py tests/test_server_verification.py
git commit -m "feat: add server verification success path"
```

### Task 4: Add Cleanup Truth, Failure Priority, And Remaining Failure Matrix

**Files:**
- Modify: `src/local_ai_control_center_installer/server_verification.py`
- Modify: `tests/test_server_verification.py`

- [ ] **Step 1: Write the failing failure-matrix tests**

Add to `tests/test_server_verification.py`:

```python
def test_apply_server_verification_maps_port_selection_failure_to_server_port_bind(
    tmp_path: Path,
):
    session = _build_runtime_ready_session(tmp_path)

    updated = apply_server_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        select_port=lambda host="127.0.0.1": (_ for _ in ()).throw(OSError("busy")),
        process_factory=lambda command, log_path: None,
        health_probe=lambda base_url: "ready",
        stop_process=lambda proc: True,
        now_fn=_fake_now([0.0]),
        sleep_fn=lambda _: None,
    )

    assert updated.server_verification_status == "failed"
    assert updated.server_process_status == "failed"
    assert updated.server_health_status == "skipped"
    assert updated.failing_step == "server-port-bind"


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
        now_fn=_fake_now([0.0, 0.1, 0.2, 0.3, 20.5]),
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
    assert updated.error_message is not None
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_server_verification.py::test_apply_server_verification_maps_port_selection_failure_to_server_port_bind tests/test_server_verification.py::test_apply_server_verification_marks_server_health_failure_after_timeout tests/test_server_verification.py::test_apply_server_verification_maps_process_death_during_health_polling_to_server_process_start tests/test_server_verification.py::test_apply_server_verification_maps_stop_failure_after_success_to_server_process_stop tests/test_server_verification.py::test_apply_server_verification_preserves_earlier_failure_when_cleanup_also_fails -v`
Expected: FAIL because the failure matrix and cleanup priority rules are not complete yet

- [ ] **Step 3: Implement the remaining failure rules**

Complete `apply_server_verification()` with:

- `server-port-bind` mapping when port selection fails before process start
- `server-process-start` mapping when the process dies during health polling before readiness is reached
- `server-health` mapping when health never becomes ready before timeout
- cleanup handling through an injected/default `stop_process`
- failure-step priority:
  - if success had already been reached, cleanup failure becomes `server-process-stop`
  - if an earlier failure already happened, keep that earlier `failing_step`
  - record cleanup failure details in `error_message`

Add a default stop helper:

```python
def stop_server_process(
    process,
    *,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    timeout_seconds: float = 5.0,
) -> bool:
    process.terminate()
    deadline = now_fn() + timeout_seconds
    while now_fn() < deadline:
        if process.poll() is not None:
            return True
        sleep_fn(0.1)
    process.kill()
    return False
```

- [ ] **Step 4: Run the full server verification test file**

Run: `python -m pytest tests/test_server_verification.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/server_verification.py tests/test_server_verification.py
git commit -m "feat: add server verification failure rules"
```

### Task 5: Wire Defaults, Main Exit Truth, And Injected Smoke Coverage

**Files:**
- Modify: `src/local_ai_control_center_installer/defaults.py`
- Modify: `src/local_ai_control_center_installer/main.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_package_smoke.py`

- [ ] **Step 1: Write the failing orchestration and CLI tests**

Add to `tests/test_main.py`:

```python
def test_run_installer_calls_server_verification_after_runtime_and_before_reporting():
    events: list[str] = []

    def fake_apply(session: InstallerSession, **_):
        events.append("bootstrap")
        session.bootstrap_status = "ready"
        return session

    def fake_runtime(session: InstallerSession, **_):
        events.append("runtime")
        session.runtime_payload_status = "ready"
        return session

    def fake_server_verification(session: InstallerSession, **_):
        events.append("server")
        session.server_verification_status = "ready"
        return session

    def fake_write_reports(session: InstallerSession, **_):
        events.append("report")

    run_installer(
        collect_answers=lambda session: session,
        scan_dependencies=lambda session: session,
        apply_phase=fake_apply,
        apply_runtime_payload=fake_runtime,
        apply_server_verification=fake_server_verification,
        write_reports=fake_write_reports,
    )

    assert events == ["bootstrap", "runtime", "server", "report"]


def test_main_returns_non_zero_when_server_verification_status_is_failed(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        main_module,
        "run_installer",
        lambda: {
            "bootstrap_status": "ready",
            "runtime_payload_status": "ready",
            "server_verification_status": "failed",
        },
    )

    assert main_module.main() == 1
```

Also update the existing success-path test already in `tests/test_main.py`:

- `test_main_delegates_to_run_installer_and_returns_zero`

Its stubbed `run_installer()` payload must now include:

```python
"server_verification_status": "ready",
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_main.py::test_run_installer_calls_server_verification_after_runtime_and_before_reporting tests/test_main.py::test_main_returns_non_zero_when_server_verification_status_is_failed -v`
Expected: FAIL because `main.py` does not yet call a server-verification step or require it for exit `0`

- [ ] **Step 3: Wire defaults and main**

In `defaults.py`, add:

```python
from local_ai_control_center_installer.server_verification import apply_server_verification


def default_apply_server_verification(session: InstallerSession) -> InstallerSession:
    return apply_server_verification(session, temp_root=_default_temp_root())
```

In `main.py`, extend `run_installer()`:

```python
def run_installer(
    *,
    collect_answers: SessionStep | None = None,
    scan_dependencies: SessionStep | None = None,
    apply_phase: SessionStep | None = None,
    apply_runtime_payload: SessionStep | None = None,
    apply_server_verification: SessionStep | None = None,
    write_reports: ReportStep | None = None,
):
    ...
    session = apply_phase(session)
    session = apply_runtime_payload(session)
    session = apply_server_verification(session)
    write_reports(session)
```

Update `main()` so exit `0` now requires:

- `bootstrap_status == "ready"`
- `runtime_payload_status == "ready"`
- `server_verification_status == "ready"`

- [ ] **Step 4: Update the injected smoke test and the existing real-default-path tests**

Modify `tests/test_package_smoke.py`:

```python
result = run_installer(
    collect_answers=lambda session: session,
    scan_dependencies=lambda session: session,
    apply_phase=lambda session: session,
    apply_runtime_payload=lambda session: session,
    apply_server_verification=lambda session: session,
    write_reports=lambda session: None,
)
```

In `tests/test_main.py`, add a helper next to `_mark_runtime_ready(...)`:

```python
def _mark_server_verification_ready(session: InstallerSession, tmp_path) -> InstallerSession:
    log_path = (
        tmp_path
        / "temp-runs"
        / "LocalAIControlCenterInstaller"
        / "runs"
        / session.started_at.replace(":", "-")
        / "llama-server.log"
    )
    session.server_verification_status = "ready"
    session.server_process_status = "ready"
    session.server_health_status = "ready"
    session.verified_server_port = 8080
    session.verified_server_url = "http://127.0.0.1:8080"
    session.server_log_path = str(log_path)
    return session
```

Update these existing tests so they do not accidentally invoke the real verifier after `run_installer()` gains the new default phase:

- `test_run_installer_uses_real_default_scan_apply_and_write_paths`
- `test_run_installer_real_default_path_converts_install_root_report_persistence_error_to_failed_result`

In both tests, monkeypatch:

```python
monkeypatch.setattr(
    defaults_module,
    "default_apply_server_verification",
    lambda session: _mark_server_verification_ready(session, tmp_path),
)
```

- [ ] **Step 5: Run the targeted main and smoke tests**

Run: `python -m pytest tests/test_main.py tests/test_package_smoke.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_ai_control_center_installer/defaults.py src/local_ai_control_center_installer/main.py tests/test_main.py tests/test_package_smoke.py
git commit -m "feat: wire server verification orchestration"
```

### Task 6: Update README Slice Status And Run Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the status note in README**

Replace the runtime-payload-only status language with a server-verification-aware note.

State clearly that the repository now delivers:

- the numbered installer questionnaire contract
- dependency bootstrap and blocking/failure classification
- pinned runtime payload preparation for `llama.cpp`
- starter model preparation
- active model configuration
- runnable `llama.cpp` server verification
- human-readable logging and JSON reporting

State clearly that the repository still does not deliver:

- `OpenCode` verification
- `TurboQuant`
- completed product installation

- [ ] **Step 2: Run full regression verification**

Run: `python -m pytest -v`
Expected: PASS

Run: `git status --short`
Expected: only intended tracked changes for this slice remain, plus any acknowledged preexisting untracked local folders outside the slice

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: clarify server verification slice scope"
```

## Done Criteria

The slice is complete only when all of the following are true:

- server verification runs only after bootstrap and runtime payload are both ready
- the installer can resolve:
  - `active-model.json`
  - the active model file
  - `llama-server.exe`
- the verifier can start `llama-server` on a loopback port
- the verifier treats:
  - HTTP `200` + `{"status": "ok"}` as ready
  - HTTP `503` as loading/continue-polling
- process-start, health, port-bind, and cleanup failures map to truthful status fields and `failing_step` values
- cleanup failure overwrites `failing_step` only when cleanup is the first failure
- server verification truth is exposed through:
  - `server_verification_status`
  - `server_process_status`
  - `server_health_status`
  - `verified_server_port`
  - `verified_server_url`
  - `server_log_path`
- `product_installation_status` remains `incomplete`
- `main()` exits `0` only when bootstrap, runtime payload, and server verification are all ready
- all tests pass with `python -m pytest -v`

## References

- Spec: `docs/superpowers/specs/2026-05-21-windows-server-verification-design.md`
- Previous implementation plan: `docs/superpowers/plans/2026-05-21-windows-stable-runtime-payload.md`
- Product requirements: `docs/requirements/PRODUCT_REQUIREMENTS.md`
