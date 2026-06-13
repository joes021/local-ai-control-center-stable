# Windows OpenCode Bootstrap And Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next Windows installer slice for `Local AI Control Center`: install a pinned `OpenCode` artifact, generate installer-managed routing config, verify `OpenCode` can resolve the verified local runtime and active model under isolated configuration, and report truthful `OpenCode` milestone status without yet claiming a complete product install.

**Architecture:** Keep `OpenCode` work split into two focused Python modules. `opencode_bootstrap.py` owns manifest load, artifact readiness, staged download/extract/promote, metadata, and managed config generation; `opencode_verification.py` owns the single bounded `opencode --pure models local-lacc` handshake subprocess plus cleanup truth. Wire both phases into the existing installer pipeline after server verification, preserve the same injected-collaborator style used by runtime and server verification, and keep `product_installation_status` at `incomplete`.

**Tech Stack:** Python 3.11+, `pytest`, standard-library `dataclasses`, `json`, `pathlib`, `subprocess`, `tempfile`, `os`, `time`, `importlib.resources`, and existing local download/archive helpers

---

## File Map

- Modify: `README.md`
  - update slice status after `OpenCode` bootstrap and verification land
- Modify: `src/local_ai_control_center_installer/session.py`
  - add `OpenCode` artifact/verification status and report fields
- Modify: `src/local_ai_control_center_installer/reporting.py`
  - expose `OpenCode` log path in temp-run paths, persist the verification log into install-root logs, and include `OpenCode` outcomes in human/JSON reports
- Modify: `src/local_ai_control_center_installer/defaults.py`
  - wire real default `OpenCode` bootstrap and verification phases after server verification
- Modify: `src/local_ai_control_center_installer/main.py`
  - extend orchestration and CLI exit truth to include `OpenCode`
- Create: `src/local_ai_control_center_installer/manifests/windows-stable-opencode.json`
  - pinned Windows `OpenCode` artifact contract
- Create: `src/local_ai_control_center_installer/opencode_bootstrap.py`
  - manifest load, validation, artifact readiness, staging/promotion, metadata, and managed config generation
- Create: `src/local_ai_control_center_installer/opencode_verification.py`
  - isolated launch construction, bounded handshake subprocess, stdout proof parsing, and cleanup truth
- Modify: `tests/test_session.py`
  - cover `OpenCode` session serialization
- Modify: `tests/test_reporting.py`
  - cover `OpenCode` run paths, human log lines, and JSON report fields
- Modify: `tests/test_main.py`
  - cover orchestration order and CLI exit truth for `OpenCode`
- Modify: `tests/test_package_smoke.py`
  - keep injected-collaborator smoke aligned with the new pipeline
- Create: `tests/test_opencode_bootstrap.py`
  - cover manifest validation, wheel packaging, skip/fail rules, artifact readiness, and managed config generation
- Create: `tests/test_opencode_verification.py`
  - cover prerequisite failures, isolated env/command construction, handshake proof, timeout/hang handling, and cleanup truth

## Implementation Notes

- Use TDD throughout. Every new behavior starts with a failing targeted test, then the minimal implementation, then the narrowest safe refactor.
- Keep this slice narrow. Do not add prompt inference, portal UI behavior, `TurboQuant`, or generic lifecycle-manager abstractions.
- Preserve existing truthfulness rules:
  - `product_installation_status` stays `incomplete`
  - CLI success for this milestone requires `opencode_verification_status == "ready"`
  - earlier failure steps stay authoritative unless cleanup is the first failure after an otherwise successful handshake
- The `OpenCode` handshake is one bounded subprocess only:
  - effective command shape: `opencode --pure models local-lacc`
  - static leading args come from manifest `launch.verification_args`
  - the verifier appends exactly one trailing provider argument: `local-lacc`
- Normative env/constants for this slice:
  - `OPENCODE_CONFIG`
  - `OPENCODE_CONFIG_CONTENT`
  - `OPENCODE_DISABLE_MODELS_FETCH=true`
- The managed config must force:
  - provider id `local-lacc`
  - top-level model `local-lacc/<active-model-id>`
  - `enabled_providers: ["local-lacc"]`
  - `options.baseURL = <verified_server_url>/v1`
  - installer-managed marker
  - autoupdate disabled when supported
- Do not hit real network services in unit tests. Inject download, process, clock, sleep, and output parsing collaborators so tests stay deterministic.
- Reuse existing helpers from `downloads.py` for:
  - archive extraction
  - SHA-256 verification
  - required-file presence and checksum checks
  - staged tree promotion
- Keep `OpenCode` metadata local to `opencode_bootstrap.py`; do not broaden the runtime metadata helper surface unless implementation reveals a concrete duplication problem.

### Task 1: Extend Session And Reporting For OpenCode Truth

**Files:**
- Modify: `src/local_ai_control_center_installer/session.py`
- Modify: `src/local_ai_control_center_installer/reporting.py`
- Modify: `tests/test_session.py`
- Modify: `tests/test_reporting.py`

- [ ] **Step 1: Write the failing session and reporting tests**

```python
from local_ai_control_center_installer.session import InstallerSession


def test_installer_session_serializes_opencode_fields():
    session = InstallerSession(
        opencode_artifact_status="ready",
        opencode_verification_status="failed",
        opencode_process_status="ready",
        opencode_connection_status="failed",
        opencode_artifact_id="windows-opencode",
        opencode_artifact_path="C:\\LACC\\tools\\opencode",
        opencode_metadata_path="C:\\LACC\\tools\\opencode\\opencode-artifact.json",
        opencode_config_path="C:\\LACC\\config\\opencode\\managed-config.json",
        verified_opencode_command="opencode --pure models local-lacc",
        opencode_log_path="C:\\LACC\\temp\\opencode-verification.log",
    )

    payload = session.to_dict()

    assert payload["opencode_artifact_status"] == "ready"
    assert payload["opencode_verification_status"] == "failed"
    assert payload["opencode_process_status"] == "ready"
    assert payload["opencode_connection_status"] == "failed"
    assert payload["verified_opencode_command"] == "opencode --pure models local-lacc"
```

```python
import json
from pathlib import Path

from local_ai_control_center_installer.reporting import build_run_paths, persist_install_root_reports, write_human_log, write_json_report
from local_ai_control_center_installer.session import InstallerSession


def test_build_run_paths_exposes_opencode_log_path(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T20-00-00")
    assert paths.opencode_log_path == (
        tmp_path
        / "LocalAIControlCenterInstaller"
        / "runs"
        / "2026-05-21T20-00-00"
        / "opencode-verification.log"
    )


def test_write_json_report_serializes_opencode_summary(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T20-00-00")
    session = InstallerSession(
        install_root=str(tmp_path / "install-root"),
        opencode_artifact_status="ready",
        opencode_verification_status="failed",
        opencode_process_status="ready",
        opencode_connection_status="failed",
        opencode_artifact_id="windows-opencode",
        opencode_artifact_path=str(tmp_path / "install-root" / "tools" / "opencode"),
        opencode_config_path=str(tmp_path / "install-root" / "config" / "opencode" / "managed-config.json"),
        verified_opencode_command="opencode --pure models local-lacc",
        opencode_log_path=str(paths.opencode_log_path),
        failing_step="opencode-connection",
    )

    write_json_report(session, paths.json_report_path)

    payload = json.loads(paths.json_report_path.read_text(encoding="utf-8"))
    assert payload["opencode_artifact_status"] == "ready"
    assert payload["opencode_verification_status"] == "failed"
    assert payload["opencode_connection_status"] == "failed"
    assert payload["verified_opencode_command"] == "opencode --pure models local-lacc"


def test_persist_install_root_reports_copies_opencode_log(tmp_path: Path):
    install_root = tmp_path / "install-root"
    temp_log = tmp_path / "temp-runs" / "opencode-verification.log"
    temp_log.parent.mkdir(parents=True, exist_ok=True)
    temp_log.write_text("handshake ok\n", encoding="utf-8")
    session = InstallerSession(
        install_root=str(install_root),
        bootstrap_status="ready",
        opencode_log_path=str(temp_log),
    )

    persist_install_root_reports(session)

    assert (install_root / "logs" / "opencode-verification.log").read_text(encoding="utf-8") == "handshake ok\n"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_session.py::test_installer_session_serializes_opencode_fields tests/test_reporting.py::test_build_run_paths_exposes_opencode_log_path tests/test_reporting.py::test_write_json_report_serializes_opencode_summary -v`
Expected: FAIL because the session and reporting structures do not yet define `OpenCode` fields

- [ ] **Step 3: Add the minimal session and reporting fields**

Extend `InstallerSession` with conservative defaults:

```python
opencode_artifact_status: str = "skipped"
opencode_verification_status: str = "skipped"
opencode_process_status: str = "skipped"
opencode_connection_status: str = "skipped"
opencode_artifact_id: str | None = None
opencode_artifact_path: str | None = None
opencode_metadata_path: str | None = None
opencode_config_path: str | None = None
verified_opencode_command: str | None = None
opencode_log_path: str | None = None
```

Extend `RunPaths` in `reporting.py`:

```python
@dataclass
class RunPaths:
    run_dir: Path
    log_path: Path
    json_report_path: Path
    server_log_path: Path
    opencode_log_path: Path
```

Update `build_run_paths()`, `write_human_log()`, and `write_json_report()` to include all `OpenCode` status and path fields.

Update `persist_install_root_reports()` so a present temp-run `session.opencode_log_path` is copied into:

```python
install_root / "logs" / "opencode-verification.log"
```

- [ ] **Step 4: Run the targeted tests again**

Run: `python -m pytest tests/test_session.py::test_installer_session_serializes_opencode_fields tests/test_reporting.py::test_build_run_paths_exposes_opencode_log_path tests/test_reporting.py::test_write_json_report_serializes_opencode_summary tests/test_reporting.py::test_persist_install_root_reports_copies_opencode_log -v`
Expected: PASS

- [ ] **Step 5: Run the full session and reporting test files**

Run: `python -m pytest tests/test_session.py tests/test_reporting.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_ai_control_center_installer/session.py src/local_ai_control_center_installer/reporting.py tests/test_session.py tests/test_reporting.py
git commit -m "feat: add opencode session and reporting state"
```

### Task 2: Add The Pinned OpenCode Manifest Contract

**Files:**
- Create: `src/local_ai_control_center_installer/manifests/windows-stable-opencode.json`
- Create: `tests/test_opencode_bootstrap.py`

- [ ] **Step 1: Write the failing manifest and packaging tests**

```python
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from local_ai_control_center_installer.opencode_bootstrap import load_opencode_manifest


def test_load_opencode_manifest_reads_pinned_contract(tmp_path: Path):
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

    manifest = load_opencode_manifest(manifest_path)

    assert manifest["opencode_artifact"]["launch"]["verification_args"] == ["--pure", "models"]
```

```python
def test_built_wheel_contains_opencode_manifest_json(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheelhouse"
    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(wheel_dir)],
        check=True,
        cwd=repo_root,
        env=env,
    )

    wheel_path = next(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel_path) as wheel_archive:
        assert "local_ai_control_center_installer/manifests/windows-stable-opencode.json" in wheel_archive.namelist()
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_opencode_bootstrap.py::test_load_opencode_manifest_reads_pinned_contract tests/test_opencode_bootstrap.py::test_built_wheel_contains_opencode_manifest_json -v`
Expected: FAIL because the manifest file and loader do not exist yet

- [ ] **Step 3: Add the packaged manifest and loader validation**

Create `windows-stable-opencode.json` with the approved contract shape:

```json
{
  "opencode_artifact": {
    "id": "windows-opencode",
    "url": "https://github.com/anomalyco/opencode/releases/download/v1.15.7/opencode-windows-x64.zip",
    "sha256": "8ac96b52692a3daeb84a20295cc7ed43aa3c698078e802926a47aef83748eab2",
    "archive_type": "zip",
    "required_files": ["opencode.exe"],
    "required_file_sha256": {
      "opencode.exe": "c18594c5368598f242387a2b6f505039a82b628c282101e99cb4452bd7622ed1"
    },
    "install_subdir": "tools/opencode",
    "launch": {
      "executable_relative_path": "opencode.exe",
      "verification_args": ["--pure", "models"],
      "extra_env": {}
    }
  }
}
```

Create `load_opencode_manifest()` in `opencode_bootstrap.py`:

```python
def load_opencode_manifest(manifest_path=None) -> dict:
    if manifest_path is None:
        manifest_path = files("local_ai_control_center_installer.manifests").joinpath(
            "windows-stable-opencode.json"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = payload.get("opencode_artifact")
    _validate_opencode_artifact(artifact)
    return payload
```

Validate:
- required top-level `opencode_artifact`
- string fields `id`, `url`, `sha256`, `archive_type`, `install_subdir`
- `required_files` is a non-empty string list
- every checksum key exists in `required_files`
- `launch.executable_relative_path` is a string
- `launch.verification_args` equals `["--pure", "models"]`
- `launch.extra_env` is a dict

- [ ] **Step 4: Run the targeted tests again**

Run: `python -m pytest tests/test_opencode_bootstrap.py::test_load_opencode_manifest_reads_pinned_contract tests/test_opencode_bootstrap.py::test_built_wheel_contains_opencode_manifest_json -v`
Expected: PASS

- [ ] **Step 5: Add one negative manifest validation test and make it pass**

Add a failing test for invalid checksum mapping without narrowing the manifest contract beyond the spec:

```python
import pytest


def test_load_opencode_manifest_rejects_checksum_for_unknown_required_file(tmp_path: Path):
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
                    "required_file_sha256": {"missing.exe": "def456"},
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

    with pytest.raises(ValueError, match="required_files"):
        load_opencode_manifest(manifest_path)
```

Run: `python -m pytest tests/test_opencode_bootstrap.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_ai_control_center_installer/manifests/windows-stable-opencode.json src/local_ai_control_center_installer/opencode_bootstrap.py tests/test_opencode_bootstrap.py
git commit -m "feat: add opencode manifest contract"
```

### Task 3: Implement OpenCode Artifact Bootstrap And Managed Config Generation

**Files:**
- Modify: `src/local_ai_control_center_installer/opencode_bootstrap.py`
- Modify: `tests/test_opencode_bootstrap.py`

- [ ] **Step 1: Write the failing bootstrap behavior tests**

```python
from pathlib import Path

from local_ai_control_center_installer.opencode_bootstrap import apply_opencode_bootstrap
from local_ai_control_center_installer.session import InstallerSession


def test_apply_opencode_bootstrap_skips_when_server_verification_is_not_ready(tmp_path: Path):
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        server_verification_status="failed",
        install_root=str(tmp_path / "install-root"),
        install_opencode=True,
    )

    updated = apply_opencode_bootstrap(session, temp_root=tmp_path / "temp-runs")

    assert updated.opencode_artifact_status == "skipped"
    assert updated.opencode_verification_status == "skipped"


def test_apply_opencode_bootstrap_marks_ready_when_artifact_is_verified_in_place(tmp_path: Path):
    install_root = tmp_path / "install-root"
    tool_root = install_root / "tools" / "opencode"
    tool_root.mkdir(parents=True)
    (tool_root / "opencode.exe").write_text("ok", encoding="utf-8")
    (tool_root / "opencode-artifact.json").write_text(
        '{"artifact_id": "windows-opencode", "source_sha256": "artifact-sha"}',
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        server_verification_status="ready",
        install_root=str(install_root),
        install_opencode=True,
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(install_root / "config" / "active-model.json"),
    )
    Path(session.active_model_config_path).parent.mkdir(parents=True, exist_ok=True)
    Path(session.active_model_config_path).write_text(
        '{"model_id": "recommended-6gb", "model_path": "C:/LACC/models/recommended-6gb.gguf"}',
        encoding="utf-8",
    )

    updated = apply_opencode_bootstrap(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: {
            "opencode_artifact": {
                "id": "windows-opencode",
                "url": "https://example.invalid/opencode.zip",
                "sha256": "artifact-sha",
                "archive_type": "zip",
                "required_files": ["opencode.exe"],
                "required_file_sha256": {"opencode.exe": "dummy"},
                "install_subdir": "tools/opencode",
                "launch": {
                    "executable_relative_path": "opencode.exe",
                    "verification_args": ["--pure", "models"],
                    "extra_env": {},
                },
            }
        },
        verify_required_file_checksums=lambda root, checksums: True,
    )

    assert updated.opencode_artifact_status == "ready"
    assert updated.opencode_artifact_id == "windows-opencode"
    assert Path(updated.opencode_config_path).exists()
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_opencode_bootstrap.py::test_apply_opencode_bootstrap_skips_when_server_verification_is_not_ready tests/test_opencode_bootstrap.py::test_apply_opencode_bootstrap_marks_ready_when_artifact_is_verified_in_place -v`
Expected: FAIL because bootstrap behavior and config generation do not exist yet

- [ ] **Step 3: Implement the bootstrap phase**

Add `apply_opencode_bootstrap()` with this shape:

```python
def apply_opencode_bootstrap(
    session: InstallerSession,
    *,
    temp_root: Path,
    load_manifest=load_opencode_manifest,
    download_archive=None,
    extract_archive=extract_archive,
    verify_archive_sha256=verify_sha256,
    verify_required_file_checksums=verify_required_file_checksums,
    write_managed_config=None,
) -> InstallerSession:
    ...
```

Required behavior:
- skip everything when server verification is not ready
- skip everything when `install_opencode` is `False`
- load manifest or map `ValueError` to `failing_step = "opencode-manifest"`
- if `verified_server_url` is missing, `active-model.json` is missing, or the active model id cannot be resolved while building managed config, fail early with:
  - `opencode_artifact_status = "ready"` only if the artifact is already valid
  - `opencode_verification_status = "failed"`
  - `opencode_process_status = "skipped"`
  - `opencode_connection_status = "skipped"`
  - `failing_step = "opencode-verification-prerequisites"`
- set:
  - `opencode_artifact_id`
  - `opencode_artifact_path`
  - `opencode_metadata_path`
  - `opencode_config_path`
- detect in-place readiness using:
  - required files
  - required file checksums
  - `opencode-artifact.json` containing artifact id and source checksum
- if not ready, stage archive to temp, verify, extract, write metadata, and promote into install root
- generate `config/opencode/managed-config.json`
- leave `opencode_verification_status` at `skipped` after bootstrap success; verification happens in the next task
- on config-write failure set:
  - `opencode_artifact_status = "ready"`
  - `opencode_verification_status = "failed"`
  - `opencode_process_status = "skipped"`
  - `opencode_connection_status = "skipped"`
  - `failing_step = "opencode-config"`

Leave `active model file exists on disk` as a verification-phase prerequisite rather than a bootstrap-phase requirement. Bootstrap only needs the active model id plus verified server URL to generate managed routing config.

Write managed config with the required local route:

```python
{
  "installer_managed": True,
  "autoupdate": False,
  "model": f"local-lacc/{model_id}",
  "enabled_providers": ["local-lacc"],
  "providers": {
    "local-lacc": {
      "provider": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": f"{verified_server_url}/v1"
      },
      "models": {
        model_id: {}
      }
    }
  }
}
```

- [ ] **Step 4: Add artifact download/failure/config tests and make them pass**

Add focused tests for:
- `install_opencode == False` leaves statuses skipped
- missing/invalid manifest maps to `opencode-manifest`
- failed archive verification maps to `opencode-artifact`
- config write failure maps to `opencode-config`
- generated config contains `local-lacc`, `enabled_providers`, and `<verified_server_url>/v1`

Run: `python -m pytest tests/test_opencode_bootstrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/opencode_bootstrap.py tests/test_opencode_bootstrap.py
git commit -m "feat: add opencode bootstrap phase"
```

### Task 4: Implement The Single-Process OpenCode Verification Handshake

**Files:**
- Create: `src/local_ai_control_center_installer/opencode_verification.py`
- Create: `tests/test_opencode_verification.py`

- [ ] **Step 1: Write the failing prerequisite and success-path tests**

```python
from pathlib import Path

from local_ai_control_center_installer.opencode_verification import apply_opencode_verification
from local_ai_control_center_installer.session import InstallerSession


class FakeProcess:
    def __init__(self, *, stdout_text: str, poll_results: list[int | None]):
        self.stdout_text = stdout_text
        self._poll_results = iter(poll_results)

    def poll(self):
        return next(self._poll_results, 0)

    def communicate(self, timeout=None):
        return (self.stdout_text, "")

    def terminate(self):
        return None

    def kill(self):
        return None


def test_apply_opencode_verification_skips_when_artifact_is_not_ready(tmp_path: Path):
    session = InstallerSession(
        opencode_artifact_status="failed",
        install_root=str(tmp_path / "install-root"),
    )

    updated = apply_opencode_verification(session, temp_root=tmp_path / "temp-runs")

    assert updated.opencode_verification_status == "skipped"
    assert updated.opencode_process_status == "skipped"
    assert updated.opencode_connection_status == "skipped"


def test_apply_opencode_verification_marks_ready_when_models_output_contains_active_model(tmp_path: Path):
    install_root = tmp_path / "install-root"
    executable = install_root / "tools" / "opencode" / "opencode.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("ok", encoding="utf-8")
    managed_config = install_root / "config" / "opencode" / "managed-config.json"
    managed_config.parent.mkdir(parents=True, exist_ok=True)
    model_path = install_root / "models" / "recommended-6gb.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("ok", encoding="utf-8")
    managed_config.write_text(
        '{"model":"local-lacc/recommended-6gb","enabled_providers":["local-lacc"],"providers":{"local-lacc":{"provider":"@ai-sdk/openai-compatible","options":{"baseURL":"http://127.0.0.1:8080/v1"},"models":{"recommended-6gb":{}}}}}',
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="ready",
        server_verification_status="ready",
        opencode_artifact_status="ready",
        opencode_artifact_path=str(install_root / "tools" / "opencode"),
        opencode_config_path=str(managed_config),
        verified_server_url="http://127.0.0.1:8080",
        active_model_config_path=str(install_root / "config" / "active-model.json"),
    )
    Path(session.active_model_config_path).parent.mkdir(parents=True, exist_ok=True)
    Path(session.active_model_config_path).write_text(
        f'{{"model_id": "recommended-6gb", "model_path": "{model_path.as_posix()}"}}',
        encoding="utf-8",
    )

    updated = apply_opencode_verification(
        session,
        temp_root=tmp_path / "temp-runs",
        process_factory=lambda command, env, cwd, log_path: FakeProcess(
            stdout_text="local-lacc/recommended-6gb\n",
            poll_results=[None, 0],
        ),
        stop_process=lambda process, **_: True,
    )

    assert updated.opencode_verification_status == "ready"
    assert updated.opencode_process_status == "ready"
    assert updated.opencode_connection_status == "ready"
    assert updated.verified_opencode_command == "opencode --pure models local-lacc"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_opencode_verification.py::test_apply_opencode_verification_skips_when_artifact_is_not_ready tests/test_opencode_verification.py::test_apply_opencode_verification_marks_ready_when_models_output_contains_active_model -v`
Expected: FAIL because the verification module does not exist yet

- [ ] **Step 3: Implement the bounded verification module**

Create:

```python
def apply_opencode_verification(
    session: InstallerSession,
    *,
    temp_root: Path,
    load_manifest=load_opencode_manifest,
    process_factory=None,
    stop_process=None,
    now_fn=None,
    sleep_fn=None,
) -> InstallerSession:
    ...
```

Required behavior:
- skip when `opencode_artifact_status != "ready"`
- resolve prerequisites:
  - `verified_server_url`
  - `active-model.json`
  - active model file exists
  - `opencode.exe` exists under `opencode_artifact_path`
  - managed config file exists
- reload the packaged `OpenCode` manifest to obtain the launch contract, especially `launch.extra_env`
- map missing prerequisite to `opencode-verification-prerequisites`
- build the exact command:

```python
[
    str(opencode_executable),
    "--pure",
    "models",
    "local-lacc",
]
```

- set env:

```python
{
    "OPENCODE_CONFIG": str(managed_config_path),
    "OPENCODE_CONFIG_CONTENT": json.dumps(
        {
            "model": f"local-lacc/{model_id}",
            "enabled_providers": ["local-lacc"],
            "providers": {
                "local-lacc": {
                    "provider": "@ai-sdk/openai-compatible",
                    "options": {
                        "baseURL": f"{verified_server_url}/v1"
                    },
                    "models": {
                        model_id: {}
                    }
                }
            }
        }
    ),
    "OPENCODE_DISABLE_MODELS_FETCH": "true",
}
```

- use an empty temporary working directory
- derive the temp log path from the same `run_id` pattern already used by `reporting.build_run_paths()`
- store `verified_opencode_command`
- store `opencode_log_path`
- use `process_factory(command, env, cwd, log_path)` to launch a `Popen`-like process
- capture combined stdout/stderr from the bounded verification subprocess and write that content into `log_path` before evaluating the handshake result
- wait on the same subprocess for bounded output collection
- use `stop_process(process, now_fn=..., sleep_fn=..., timeout_seconds=...)` for terminate/kill cleanup when the subprocess hangs or remains alive unexpectedly
- merge manifest `launch.extra_env` into the verification environment without allowing it to override `OPENCODE_CONFIG`, `OPENCODE_CONFIG_CONTENT`, or `OPENCODE_DISABLE_MODELS_FETCH`
- succeed only when:
  - exit code is `0`
  - stdout contains `local-lacc/<active-model-id>`
  - generated config already contains `<verified_server_url>/v1`

- [ ] **Step 4: Add the failure-mode tests and make them pass**

Add focused tests for:
- missing `verified_server_url` maps to `opencode-verification-prerequisites`
- non-zero exit maps to `opencode-process-start`
- zero exit without the model token maps to `opencode-connection`
- hung subprocess before a successful handshake keeps the earlier primary failure step and does not upgrade itself to `opencode-process-stop`
- cleanup failure after an otherwise successful handshake maps to `opencode-process-stop`
- env contains `OPENCODE_CONFIG`, `OPENCODE_CONFIG_CONTENT`, `OPENCODE_DISABLE_MODELS_FETCH`
- manifest `extra_env` is merged, but cannot override the normative `OPENCODE_*` variables
- verification log file contains the combined subprocess output used for handshake evaluation
- cwd is a temp verification directory, not repo root

Use a fake process contract like:

```python
class FakeProcess:
    def __init__(self, *, stdout_text: str, poll_results: list[int | None]):
        self.stdout_text = stdout_text
        self._poll_results = iter(poll_results)

    def poll(self):
        return next(self._poll_results, None)

    def communicate(self, timeout=None):
        return (self.stdout_text, "")

    def terminate(self):
        ...

    def kill(self):
        ...
```

Run: `python -m pytest tests/test_opencode_verification.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/opencode_verification.py tests/test_opencode_verification.py
git commit -m "feat: add opencode verification handshake"
```

### Task 5: Wire OpenCode Into Defaults, Main, And Smoke Tests

**Files:**
- Modify: `src/local_ai_control_center_installer/defaults.py`
- Modify: `src/local_ai_control_center_installer/main.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_package_smoke.py`

- [ ] **Step 1: Write the failing orchestration and exit-gate tests**

```python
def test_run_installer_calls_opencode_steps_after_server_verification_and_before_reporting():
    events = []

    def fake_bootstrap(session):
        events.append("bootstrap")
        session.bootstrap_status = "ready"
        return session

    def fake_runtime(session):
        events.append("runtime")
        session.runtime_payload_status = "ready"
        return session

    def fake_server(session):
        events.append("server")
        session.server_verification_status = "ready"
        return session

    def fake_opencode_bootstrap(session):
        events.append("opencode-bootstrap")
        session.opencode_artifact_status = "ready"
        return session

    def fake_opencode_verify(session):
        events.append("opencode-verify")
        session.opencode_verification_status = "ready"
        return session

    run_installer(
        collect_answers=lambda session: session,
        scan_dependencies=lambda session: session,
        apply_phase=fake_bootstrap,
        apply_runtime_payload=fake_runtime,
        apply_server_verification=fake_server,
        apply_opencode_bootstrap=fake_opencode_bootstrap,
        apply_opencode_verification=fake_opencode_verify,
        write_reports=lambda session: events.append("report"),
    )

    assert events == [
        "bootstrap",
        "runtime",
        "server",
        "opencode-bootstrap",
        "opencode-verify",
        "report",
    ]
```

```python
def test_main_returns_non_zero_when_opencode_verification_status_is_failed(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "run_installer",
        lambda: {
            "bootstrap_status": "ready",
            "runtime_payload_status": "ready",
            "server_verification_status": "ready",
            "opencode_verification_status": "failed",
        },
    )

    assert main_module.main() == 1
```

```python
def test_run_installer_keeps_product_installation_incomplete_after_opencode_success():
    result = run_installer(
        collect_answers=lambda session: session,
        scan_dependencies=lambda session: session,
        apply_phase=lambda session: setattr(session, "bootstrap_status", "ready") or session,
        apply_runtime_payload=lambda session: setattr(session, "runtime_payload_status", "ready") or session,
        apply_server_verification=lambda session: setattr(session, "server_verification_status", "ready") or session,
        apply_opencode_bootstrap=lambda session: setattr(session, "opencode_artifact_status", "ready") or session,
        apply_opencode_verification=lambda session: setattr(session, "opencode_verification_status", "ready") or session,
        write_reports=lambda session: None,
    )

    assert result["product_installation_status"] == "incomplete"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python -m pytest tests/test_main.py::test_run_installer_calls_opencode_steps_after_server_verification_and_before_reporting tests/test_main.py::test_main_returns_non_zero_when_opencode_verification_status_is_failed tests/test_package_smoke.py -v`
Expected: FAIL because `run_installer()` and the smoke test do not yet know about `OpenCode` phases

- [ ] **Step 3: Wire the new pipeline stages**

Update `main.py`:

```python
def run_installer(
    *,
    collect_answers=None,
    scan_dependencies=None,
    apply_phase=None,
    apply_runtime_payload=None,
    apply_server_verification=None,
    apply_opencode_bootstrap=None,
    apply_opencode_verification=None,
    write_reports=None,
):
    ...
    session = apply_phase(session)
    session = apply_runtime_payload(session)
    session = apply_server_verification(session)
    session = apply_opencode_bootstrap(session)
    session = apply_opencode_verification(session)
    write_reports(session)
```

Update CLI success gate:

```python
if (
    result.get("bootstrap_status") == "ready"
    and result.get("runtime_payload_status") == "ready"
    and result.get("server_verification_status") == "ready"
    and result.get("opencode_verification_status") == "ready"
):
    return 0
```

Update `defaults.py` with:

```python
def default_apply_opencode_bootstrap(session: InstallerSession) -> InstallerSession:
    return apply_opencode_bootstrap(session, temp_root=_default_temp_root())


def default_apply_opencode_verification(session: InstallerSession) -> InstallerSession:
    return apply_opencode_verification(session, temp_root=_default_temp_root())
```

Update package smoke to inject both new collaborators.

- [ ] **Step 4: Run the targeted tests again**

Run: `python -m pytest tests/test_main.py tests/test_package_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/defaults.py src/local_ai_control_center_installer/main.py tests/test_main.py tests/test_package_smoke.py
git commit -m "feat: wire opencode installer phases"
```

### Task 6: Update README And Run Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing documentation expectation as a checklist item in the task notes**

Update `README.md` so `Current Slice Status` becomes truthful:

- move `OpenCode` from “does not yet deliver” to “already delivers”
- keep `TurboQuant` and completed product installation in the “does not yet deliver” list
- mention that the current milestone verifies installer-managed `OpenCode` routing but not yet first inference smoke

- [ ] **Step 2: Edit the README**

Expected content shape:

```markdown
This slice already delivers:

- ...
- installer-managed `OpenCode` artifact preparation
- installer-managed `OpenCode` verification against the active local runtime/model route
- human-readable logging and JSON reporting

This slice does not yet deliver:

- first-run `OpenCode` inference smoke
- `TurboQuant`
- completed product installation
```

- [ ] **Step 3: Run the focused regression set**

Run: `python -m pytest tests/test_session.py tests/test_reporting.py tests/test_opencode_bootstrap.py tests/test_opencode_verification.py tests/test_main.py tests/test_package_smoke.py -v`
Expected: PASS

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update opencode slice status"
```

## Final Verification Checklist

- [ ] `windows-stable-opencode.json` is packaged into the wheel
- [ ] `apply_opencode_bootstrap()` skips cleanly when `install_opencode == False`
- [ ] `apply_opencode_bootstrap()` maps manifest, artifact, and config failures to the correct failure steps
- [ ] managed config contains `local-lacc`, `enabled_providers`, and `<verified_server_url>/v1`
- [ ] `apply_opencode_verification()` uses the exact `opencode --pure models local-lacc` command shape
- [ ] `apply_opencode_verification()` uses `OPENCODE_CONFIG`, `OPENCODE_CONFIG_CONTENT`, and `OPENCODE_DISABLE_MODELS_FETCH=true`
- [ ] `run_installer()` order is `collect -> scan -> bootstrap -> runtime -> server -> opencode bootstrap -> opencode verification -> report`
- [ ] CLI exit `0` now requires `opencode_verification_status == "ready"`
- [ ] `product_installation_status` remains `incomplete`
- [ ] `README.md` truthfully separates milestone success from full product completion


