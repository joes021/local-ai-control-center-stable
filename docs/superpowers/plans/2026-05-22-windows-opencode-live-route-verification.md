# Windows OpenCode Live-Route Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the Windows `OpenCode` installer milestone so success proves a real bounded inference request reached an installer-owned local runtime route, while keeping `opencode_log_path` and user-facing reporting strictly truthful.

**Architecture:** Keep the follow-up centered in `opencode_verification.py` instead of adding a new installer phase. The verifier should start a temporary `llama-server`, place a narrow installer-owned relay in front of it, launch a bounded `OpenCode --pure run` smoke with a unique marker, and mark success only when the relay sees that marker and the upstream runtime returns a valid response. Reporting stays truthful by never persisting nonexistent `OpenCode` log paths and by updating README/human-log wording to describe `installer-managed OpenCode live-route verification`.

**Tech Stack:** Python 3.11+, `pytest`, standard-library `dataclasses`, `json`, `pathlib`, `subprocess`, `tempfile`, `time`, `uuid`, `socket`, `threading`, `http.server`, `urllib.request`, and existing local installer/reporting helpers

---

## File Map

- Modify: `README.md`
  - update slice wording from generic `OpenCode` route verification to installer-managed live-route verification, while keeping first-run user smoke out of scope
- Modify: `src/local_ai_control_center_installer/manifests/windows-stable-opencode.json`
  - replace the old `--pure models` launch contract with the bounded `--pure run --format json --model` smoke prefix
- Modify: `src/local_ai_control_center_installer/opencode_bootstrap.py`
  - validate the new packaged `OpenCode` launch contract shape without widening bootstrap scope
- Modify: `src/local_ai_control_center_installer/opencode_verification.py`
  - replace config/stdout handshake proof with temporary runtime + relay + marker-based inference smoke, preserve truthful failure mapping, and stop assigning dead `opencode_log_path` values
- Modify: `src/local_ai_control_center_installer/reporting.py`
  - serialize `opencode_log_path` only when it points at a real file and keep persisted reports truthful during promotion/rollback
- Modify: `tests/test_opencode_bootstrap.py`
  - cover the new manifest `verification_args` contract
- Modify: `tests/test_opencode_verification.py`
  - replace old handshake tests with bounded smoke, relay proof, partial-proof truth, runtime/relay startup failures, and log-path truth coverage
- Modify: `tests/test_reporting.py`
  - cover dead-log-path sanitization and the new human-log wording
- Modify: `tests/test_session.py`
  - keep serialized `verified_opencode_command` expectations aligned with the new bounded smoke command
- Modify: `tests/test_main.py`
  - keep any snapshot-style `verified_opencode_command` expectations aligned with the new smoke command string if they currently assert the old `--pure models` form

## Implementation Notes

- Use TDD throughout. Each new behavior starts with a failing targeted test, then the minimum implementation, then the narrowest safe refactor.
- Keep this follow-up narrow:
  - do not add a new installer phase
  - do not claim completed product installation
  - do not add user-facing first-run interactive smoke
  - do not broaden into `TurboQuant`, browser UX, or update flows
- The persisted installer-managed config on disk must stay pointed at the already-verified runtime URL:
  - `providers.local-lacc.options.baseURL = <verified_server_url>/v1`
- The relay URL is verification-only state:
  - it may appear only inside the runtime `OPENCODE_CONFIG_CONTENT` override for the bounded verifier run
  - it must never be written back into the persisted install-root config
- Keep `OPENCODE_DISABLE_MODELS_FETCH=true` authoritative during live-route verification even if manifest `extra_env` tries to override it.
- `verified_opencode_command` should become testable and deterministic:
  - inject `marker_factory` in tests so the prompt token is stable
  - store the full bounded smoke command string, not the old `models` handshake command
- Preserve the spec’s truth table:
  - `opencode-runtime-server-start`
  - `opencode-relay-start`
  - `opencode-inference-smoke`
  - `opencode-live-route-proof`
  - `opencode-process-stop`
- Preserve the strongest truthful signal available:
  - process fails after marker seen + upstream success => `opencode_verification_status = failed`, `opencode_process_status = failed`, `opencode_connection_status = ready`
  - marker seen + upstream invalid/failed => `failing_step = opencode-live-route-proof`, `opencode_connection_status = failed`
- Do not hit real network services in unit tests. Inject runtime launch, relay launch, process launch, cleanup, clock, and marker collaborators so tests stay deterministic.

### Task 1: Update The Packaged OpenCode Launch Contract

**Files:**
- Modify: `src/local_ai_control_center_installer/manifests/windows-stable-opencode.json`
- Modify: `src/local_ai_control_center_installer/opencode_bootstrap.py`
- Modify: `tests/test_opencode_bootstrap.py`

- [ ] **Step 1: Write the failing manifest-contract tests**

```python
def test_load_opencode_manifest_accepts_bounded_run_verification_args(tmp_path: Path):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://example.invalid/opencode.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["opencode.exe"],
                    "required_file_sha256": {"opencode.exe": "def456"},
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": ["--pure", "run", "--format", "json", "--model"],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    payload = load_opencode_manifest(manifest_path)

    assert payload["opencode_artifact"]["launch"]["verification_args"] == [
        "--pure",
        "run",
        "--format",
        "json",
        "--model",
    ]
```

```python
def test_load_opencode_manifest_rejects_legacy_models_handshake_args(tmp_path: Path):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://example.invalid/opencode.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["opencode.exe"],
                    "required_file_sha256": {"opencode.exe": "def456"},
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": ["--pure", "models"],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="verification_args"):
        load_opencode_manifest(manifest_path)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_opencode_bootstrap.py::test_load_opencode_manifest_accepts_bounded_run_verification_args tests/test_opencode_bootstrap.py::test_load_opencode_manifest_rejects_legacy_models_handshake_args -v`
Expected: FAIL because the packaged launch contract and loader still require `["--pure", "models"]`

- [ ] **Step 3: Update the packaged manifest and loader validation**

Set the packaged manifest launch prefix to:

```json
"launch": {
  "executable_relative_path": "opencode.exe",
  "verification_args": ["--pure", "run", "--format", "json", "--model"],
  "extra_env": {}
}
```

Tighten `opencode_bootstrap.py` validation so `verification_args` must equal:

```python
["--pure", "run", "--format", "json", "--model"]
```

Do not add the dynamic model id or prompt to the packaged manifest. Those stay verifier-owned runtime values in `opencode_verification.py`.

- [ ] **Step 4: Run the targeted tests again**

Run: `python -m pytest tests/test_opencode_bootstrap.py::test_load_opencode_manifest_accepts_bounded_run_verification_args tests/test_opencode_bootstrap.py::test_load_opencode_manifest_rejects_legacy_models_handshake_args -v`
Expected: PASS

- [ ] **Step 5: Run the full bootstrap test file**

Run: `python -m pytest tests/test_opencode_bootstrap.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_ai_control_center_installer/manifests/windows-stable-opencode.json src/local_ai_control_center_installer/opencode_bootstrap.py tests/test_opencode_bootstrap.py
git commit -m "feat: update opencode launch contract for live-route smoke"
```

### Task 2: Make OpenCode Log-Path Reporting Strictly Truthful

**Files:**
- Modify: `src/local_ai_control_center_installer/opencode_verification.py`
- Modify: `src/local_ai_control_center_installer/reporting.py`
- Modify: `tests/test_opencode_verification.py`
- Modify: `tests/test_reporting.py`

- [ ] **Step 1: Write the failing log-truth tests**

```python
def test_apply_opencode_verification_keeps_log_path_unset_when_prerequisites_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    session.verified_server_url = None

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(
            verification_args=["--pure", "run", "--format", "json", "--model"]
        ),
    )

    updated = apply_opencode_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.failing_step == "opencode-verification-prerequisites"
    assert updated.opencode_log_path is None
```

```python
def test_persist_install_root_reports_does_not_serialize_dead_opencode_log_path(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        install_root=str(install_root),
        opencode_log_path=str(tmp_path / "missing" / "opencode-verification.log"),
    )

    persist_install_root_reports(session)

    report_payload = json.loads(
        (install_root / "logs" / "install-report.json").read_text(encoding="utf-8")
    )
    session_payload = json.loads(
        (install_root / "config" / "installer-session.json").read_text(encoding="utf-8")
    )

    assert report_payload["opencode_log_path"] is None
    assert session_payload["opencode_log_path"] is None
    assert session.opencode_log_path is None
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_opencode_verification.py::test_apply_opencode_verification_keeps_log_path_unset_when_prerequisites_fail tests/test_reporting.py::test_persist_install_root_reports_does_not_serialize_dead_opencode_log_path -v`
Expected: FAIL because the verifier assigns the temp log path before any file exists and reporting currently serializes stale paths unchanged

- [ ] **Step 3: Implement strict log-path truth**

In `opencode_verification.py`:

- stop assigning `session.opencode_log_path` immediately after `build_run_paths()`
- assign it only after `_write_log_text()` succeeds or after a log file is otherwise confirmed to exist
- when `_write_log_text()` fails, keep the earlier failure authoritative and leave `session.opencode_log_path` unset

In `reporting.py` add a narrow sanitizer helper such as:

```python
def _normalize_optional_existing_file(raw_path: str | None) -> str | None:
    normalized = (raw_path or "").strip()
    if not normalized:
        return None
    candidate = Path(normalized)
    if not candidate.exists() or not candidate.is_file():
        return None
    return str(candidate)
```

Use that helper in:

- `write_human_log()`
- `write_json_report()`
- `persist_install_root_reports()`

So reports remain truthful even if a stale in-memory path is present from an earlier code path or from a manually loaded session snapshot.

Also make the truth canonical before any staged writes:

```python
normalized_log_path = _normalize_optional_existing_file(session.opencode_log_path)
session.opencode_log_path = normalized_log_path
```

Apply that canonicalization before:

- `write_human_log()`
- `write_json_report()`
- `write_session_snapshot()`

so `installer-session.json`, the in-memory session object, and the persisted report all agree on `None` for nonexistent logs.

- [ ] **Step 4: Add one more regression for early process-launch failure**

Add a focused test that `process_factory` raising before output collection leaves no dead temp log path behind:

```python
assert updated.opencode_log_path is None
```

Run: `python -m pytest tests/test_opencode_verification.py tests/test_reporting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/opencode_verification.py src/local_ai_control_center_installer/reporting.py tests/test_opencode_verification.py tests/test_reporting.py
git commit -m "fix: keep opencode log path truthful"
```

### Task 3: Replace The Old Handshake With Live-Route Inference Proof

**Files:**
- Modify: `src/local_ai_control_center_installer/opencode_verification.py`
- Modify: `tests/test_opencode_verification.py`

- [ ] **Step 1: Rewrite the success-path test around the new bounded smoke**

```python
def test_apply_opencode_verification_marks_ready_only_after_live_route_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session = _build_ready_session(tmp_path)
    proof_state = RelayProofState(
        marker_seen=True,
        upstream_success=True,
        response_has_assistant_content=True,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "local_ai_control_center_installer.opencode_verification.load_opencode_manifest",
        lambda: _build_manifest(
            verification_args=["--pure", "run", "--format", "json", "--model"]
        ),
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        marker_factory=lambda: "LACC_VERIFY_MARKER:test-marker",
        runtime_server_factory=lambda command, log_path: FakeRuntimeHandle(),
        relay_factory=lambda *, marker, upstream_base_url: FakeRelayHandle(
            base_url="http://127.0.0.1:9090",
            proof_state=proof_state,
        ),
        process_factory=lambda command, *, cwd, env, log_path: _capture_process(
            captured,
            command=command,
            env=env,
            cwd=cwd,
            log_path=log_path,
            stdout='{"ok":true}\n',
            returncode=0,
        ),
        stop_process=lambda process, **_: True,
        stop_runtime=lambda runtime, **_: True,
        stop_relay=lambda relay, **_: True,
    )

    assert updated.opencode_verification_status == "ready"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "ready"
    assert captured["command"] == [
        str(Path(session.opencode_artifact_path) / "opencode.exe"),
        "--pure",
        "run",
        "--format",
        "json",
        "--model",
        "local-lacc/recommended-6gb",
        "Repeat this exact token once: LACC_VERIFY_MARKER:test-marker",
    ]
    embedded_config = json.loads(captured["env"]["OPENCODE_CONFIG_CONTENT"])
    assert embedded_config["providers"]["local-lacc"]["options"]["baseURL"] == "http://127.0.0.1:9090/v1"
    assert (
        Path(session.opencode_config_path).read_text(encoding="utf-8")
        .find("http://127.0.0.1:8080/v1")
        != -1
    )
```

- [ ] **Step 2: Run the targeted success-path test to verify it fails**

Run: `python -m pytest tests/test_opencode_verification.py::test_apply_opencode_verification_marks_ready_only_after_live_route_proof -v`
Expected: FAIL because the verifier still launches the old `--pure models` handshake and has no runtime/relay proof logic

- [ ] **Step 3: Add narrow internal proof helpers and collaborators**

Inside `opencode_verification.py`, keep the work in the existing module but add small focused structures such as:

```python
@dataclass
class RelayProofState:
    marker_seen: bool = False
    upstream_success: bool = False
    response_has_assistant_content: bool = False
    upstream_error: str | None = None


@dataclass
class TemporaryRuntimeHandle:
    process: object
    base_url: str
    log_path: Path


@dataclass
class VerificationRelayHandle:
    server: object
    base_url: str
    proof_state: RelayProofState
```

Prefer this orchestrator shape:

```python
def apply_opencode_verification(
    session: InstallerSession,
    *,
    temp_root: Path,
    process_factory=None,
    runtime_server_factory=None,
    relay_factory=None,
    stop_process=None,
    stop_runtime=None,
    stop_relay=None,
    marker_factory=None,
    now_fn=None,
    sleep_fn=None,
) -> InstallerSession:
    ...
```

Required runtime behavior:

- resolve the active model id/path, `opencode.exe`, managed config, and packaged launch contract
- allocate a temporary verifier runtime loopback URL
- allocate an installer-owned relay loopback URL
- generate `LACC_VERIFY_MARKER:<uuid>`
- build the exact command:

```python
[
    str(opencode_executable),
    "--pure",
    "run",
    "--format",
    "json",
    "--model",
    f"local-lacc/{model_id}",
    f"Repeat this exact token once: {marker}",
]
```

- build `OPENCODE_CONFIG_CONTENT` so the verifier run points at the relay URL, while the persisted config file on disk stays pointed at `session.verified_server_url`
- keep `OPENCODE_DISABLE_MODELS_FETCH = "true"` authoritative even if manifest `extra_env` attempts to override it
- do not treat a successful `Popen` alone as runtime readiness; the temporary runtime must become healthy before the smoke starts
- reuse the startup discipline from `server_verification.py`:
  - choose a loopback port
  - launch `llama-server.exe --host 127.0.0.1 --port <port> --model <model_path>`
  - poll `/health` on the temporary runtime with a bounded timeout window
  - map `spawn succeeded but runtime never became healthy` to `opencode-runtime-server-start`
  - only start the relay and `OpenCode` smoke after runtime health is confirmed
- capture combined stdout/stderr into the temp `opencode-verification.log`
- succeed only when:
  - the `OpenCode` process exits `0`
  - the relay saw the expected marker in `/v1/chat/completions`
  - the relay received HTTP `200`
  - the upstream response decoded as JSON
  - the upstream response included at least one assistant content payload

- [ ] **Step 4: Add the failure-truth tests before finishing the implementation**

Add targeted tests for:

- temporary runtime start failure:

```python
assert updated.failing_step == "opencode-runtime-server-start"
assert updated.opencode_process_status == "skipped"
assert updated.opencode_connection_status == "skipped"
```

- temporary runtime spawned but never passed health readiness:

```python
assert updated.failing_step == "opencode-runtime-server-start"
assert updated.opencode_process_status == "skipped"
assert updated.opencode_connection_status == "skipped"
assert "health" in updated.error_message
```

- relay start failure:

```python
assert updated.failing_step == "opencode-relay-start"
assert updated.opencode_process_status == "skipped"
assert updated.opencode_connection_status == "skipped"
```

- `OpenCode` process fails before any proof:

```python
assert updated.failing_step == "opencode-inference-smoke"
assert updated.opencode_process_status == "failed"
assert updated.opencode_connection_status == "skipped"
```

- relay never sees marker:

```python
assert updated.failing_step == "opencode-live-route-proof"
assert updated.opencode_process_status == "ready"
assert updated.opencode_connection_status == "failed"
```

- partial proof is preserved when process fails after marker + upstream success:

```python
assert updated.failing_step == "opencode-inference-smoke"
assert updated.opencode_process_status == "failed"
assert updated.opencode_connection_status == "ready"
```

- upstream proof wins when marker is seen but upstream is invalid/failed:

```python
assert updated.failing_step == "opencode-live-route-proof"
assert updated.opencode_process_status == "failed"
assert updated.opencode_connection_status == "failed"
```

- cleanup failure after successful proof:

```python
assert updated.failing_step == "opencode-process-stop"
assert updated.opencode_process_status == "ready"
assert updated.opencode_connection_status == "ready"
```

- cleanup failure must not overwrite an older primary failure:

```python
assert updated.failing_step == "opencode-live-route-proof"
assert "failed to stop" in updated.error_message
```

- [ ] **Step 5: Add a relay-focused integration-style unit test with a real loopback server**

Keep this one narrow and standard-library only. Start the real relay helper on `127.0.0.1`, send it a synthetic `/v1/chat/completions` payload containing the marker, and back it with a fake upstream HTTP responder so the test proves:

- marker extraction looks under `messages`
- only `/v1/chat/completions` is accepted
- non-`POST` requests are rejected
- non-JSON request bodies are rejected
- invalid JSON or missing assistant content sets `upstream_success = False`

Run: `python -m pytest tests/test_opencode_verification.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_ai_control_center_installer/opencode_verification.py tests/test_opencode_verification.py
git commit -m "feat: prove opencode live route with bounded smoke"
```

### Task 4: Update Reporting Wording, Cross-File Expectations, And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `src/local_ai_control_center_installer/reporting.py`
- Modify: `tests/test_reporting.py`
- Modify: `tests/test_session.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write the failing wording/expectation tests**

```python
def test_write_human_log_uses_live_route_wording(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-22T20-00-00")
    session = InstallerSession(
        opencode_verification_status="ready",
        opencode_connection_status="ready",
    )

    write_human_log(session, paths.log_path)

    contents = paths.log_path.read_text(encoding="utf-8")
    assert "OpenCode live-route status: ready" in contents
```

```python
def test_installer_session_serializes_live_route_smoke_command():
    session = InstallerSession(
        verified_opencode_command=(
            "opencode --pure run --format json --model "
            "local-lacc/recommended-6gb "
            "\"Repeat this exact token once: LACC_VERIFY_MARKER:test-marker\""
        )
    )

    payload = session.to_dict()

    assert "--pure run --format json --model local-lacc/recommended-6gb" in payload["verified_opencode_command"]
```

- [ ] **Step 2: Update the human-log wording and README slice status**

In `reporting.py`, keep JSON keys unchanged but make the human-readable log clearer:

```text
OpenCode verification status: ready
OpenCode process status: ready
OpenCode live-route status: ready
```

Update `README.md` so `Current Slice Status` says this slice already delivers:

- installer-managed `OpenCode` artifact preparation
- installer-managed `OpenCode` live-route verification against the active local runtime/model route

And still does not yet deliver:

- first-run end-user `OpenCode` smoke
- `TurboQuant`
- completed product installation

- [ ] **Step 3: Refresh any remaining command-string expectations**

Update tests that still pin the old command text, especially:

- `tests/test_session.py`
- `tests/test_reporting.py`
- `tests/test_main.py`

Use a deterministic marker such as `LACC_VERIFY_MARKER:test-marker` in tests so assertions stay stable.

- [ ] **Step 4: Run the focused regression set**

Run: `python -m pytest tests/test_opencode_bootstrap.py tests/test_opencode_verification.py tests/test_reporting.py tests/test_session.py tests/test_main.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add README.md src/local_ai_control_center_installer/reporting.py tests/test_reporting.py tests/test_session.py tests/test_main.py
git commit -m "docs: describe opencode live-route verification"
```

## Final Verification Checklist

- [ ] Packaged `OpenCode` manifest now requires `["--pure", "run", "--format", "json", "--model"]`
- [ ] Persisted `managed-config.json` still points at `<verified_server_url>/v1`
- [ ] Verification-only `OPENCODE_CONFIG_CONTENT` points at the installer-owned relay URL, not the persisted runtime URL
- [ ] `OPENCODE_DISABLE_MODELS_FETCH=true` stays authoritative during live-route verification
- [ ] `apply_opencode_verification()` no longer reports success from config/stdout handshake alone
- [ ] `apply_opencode_verification()` marks success only after marker seen + upstream success + assistant content
- [ ] `opencode_log_path` remains `None` when no log file was actually created
- [ ] Persisted install-root reports never point at a nonexistent `OpenCode` log
- [ ] Partial-proof truth matches the spec:
  - process failure after marker + upstream success preserves `opencode_connection_status = ready`
  - marker seen + upstream invalid/failure maps to `opencode-live-route-proof`
- [ ] `README.md` now says `installer-managed OpenCode live-route verification`
- [ ] `product_installation_status` remains `incomplete`


