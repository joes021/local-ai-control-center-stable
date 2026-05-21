# Windows Stable Runtime Payload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the second Windows installer slice for `Local AI Control Center`: a pinned runtime manifest, verified `llama.cpp` + starter model payload preparation, active model configuration, and truthful runtime reporting without yet claiming a runnable server.

**Architecture:** Keep all durable runtime behavior in the Python installer core. Add a manifest-driven runtime bootstrap step after dependency bootstrap, stage downloads in temp space, verify archives and in-place metadata, then promote only fully verified payloads into the final install root. Reuse the existing “truthful reporting first” approach so runtime readiness is explicit and `product_installation_status` stays conservative.

**Tech Stack:** Python 3.11+, `pytest`, standard-library `dataclasses`, `json`, `pathlib`, `hashlib`, `urllib.request`, `zipfile`, `shutil`, and `importlib.resources`

---

## File Map

- Modify: `pyproject.toml`
  - package runtime manifest JSON with the installer package
- Modify: `README.md`
  - update slice status after runtime payload support lands
- Modify: `src/local_ai_control_center_installer/session.py`
  - add runtime payload state and persisted runtime paths
- Modify: `src/local_ai_control_center_installer/reporting.py`
  - include runtime payload truth in human log and JSON report
- Modify: `src/local_ai_control_center_installer/defaults.py`
  - wire the default runtime payload phase after bootstrap
- Modify: `src/local_ai_control_center_installer/main.py`
  - add runtime payload collaborator to installer orchestration
- Create: `src/local_ai_control_center_installer/manifests/__init__.py`
  - make manifest data addressable as package resources
- Create: `src/local_ai_control_center_installer/manifests/windows-stable-runtime.json`
  - pinned Windows runtime artifact + starter model metadata
- Create: `src/local_ai_control_center_installer/downloads.py`
  - slice-specific checksum, extraction, metadata-marker, staging, and promote helpers
- Create: `src/local_ai_control_center_installer/runtime_bootstrap.py`
  - manifest loading, runtime orchestration, failure-state truth table, active-model config write
- Modify: `tests/test_session.py`
  - cover runtime session field defaults and serialization
- Create: `tests/test_downloads.py`
  - cover checksum, required-file layout, metadata marker, and promote rollback helpers
- Create: `tests/test_runtime_bootstrap.py`
  - cover manifest loading, bootstrap skip semantics, success path, and runtime failure matrix
- Modify: `tests/test_reporting.py`
  - cover runtime payload fields in human log and JSON report
- Modify: `tests/test_main.py`
  - cover runtime payload orchestration wiring and CLI exit mapping
- Modify: `tests/test_package_smoke.py`
  - keep the injected-collaborator smoke test aligned with the new runtime step

## Implementation Notes

- Use TDD throughout. Every new behavior starts with a failing test, then the minimal implementation, then the smallest refactor that keeps tests green.
- Do not perform real “latest release” discovery in code. The runtime manifest is pinned and versioned in-repo.
- Because runtime source URLs and checksums are temporally unstable, the execution worker must verify current official upstream values at implementation time before writing the production manifest JSON. Do not invent placeholder checksums and leave them in the final file.
- Keep `downloads.py` slice-specific. Do not turn it into a generic download framework for future phases.
- Support only the archive type that is actually pinned for this Windows slice. If the pinned runtime artifact is a `.zip`, implement only `.zip` extraction and raise clearly for unsupported archive types.
- Final runtime verification rules must follow the approved spec:
  - staged runtime archive checksum uses manifest `sha256`
  - already-promoted final runtime payload uses required-file layout + persisted metadata marker
  - `runtime_payload_status` is `skipped` when bootstrap is not `ready`
  - `product_installation_status` remains `incomplete`
- The runtime slice must repersist final install-root artifacts after runtime completes so:
  - `<install_root>\logs\install.log`
  - `<install_root>\logs\install-report.json`
  - `<install_root>\config\installer-session.json`
  reflect runtime truth rather than bootstrap-only truth.
- Avoid automated tests that perform large real downloads. Use temp directories and injected download/extract helpers instead.

### Task 1: Extend Session State For Runtime Payload Truth

**Files:**
- Modify: `src/local_ai_control_center_installer/session.py`
- Modify: `tests/test_session.py`

- [ ] **Step 1: Write the failing session test for runtime payload fields**

```python
from local_ai_control_center_installer.session import InstallerSession


def test_installer_session_serializes_runtime_payload_fields():
    session = InstallerSession(
        runtime_payload_status="ready",
        runtime_artifact_status="ready",
        starter_model="recommended-6gb",
        starter_model_status="ready",
        active_model_config_status="ready",
        runtime_artifact_id="windows-llama-cpp-runtime",
        runtime_artifact_path="C:\\LACC\\runtime\\llama.cpp",
        starter_model_path="C:\\LACC\\models\\recommended-6gb\\recommended-6gb.gguf",
        active_model_config_path="C:\\LACC\\config\\active-model.json",
        runtime_metadata_path="C:\\LACC\\runtime\\llama.cpp\\runtime-artifact.json",
    )

    payload = session.to_dict()

    assert payload["runtime_payload_status"] == "ready"
    assert payload["runtime_artifact_status"] == "ready"
    assert payload["starter_model"] == "recommended-6gb"
    assert payload["starter_model_path"].endswith("recommended-6gb.gguf")
    assert payload["runtime_metadata_path"].endswith("runtime-artifact.json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_session.py::test_installer_session_serializes_runtime_payload_fields -v`
Expected: FAIL because `InstallerSession` does not yet define the runtime payload fields

- [ ] **Step 3: Add runtime payload fields to the session model**

Add these fields to `InstallerSession` with conservative defaults:

```python
runtime_payload_status: str = "skipped"
runtime_artifact_status: str = "skipped"
starter_model_status: str = "skipped"
active_model_config_status: str = "skipped"
runtime_artifact_id: str | None = None
runtime_artifact_path: str | None = None
starter_model_path: str | None = None
active_model_config_path: str | None = None
runtime_metadata_path: str | None = None
```

Keep the existing `starter_model` field and treat it as the requested starter model id selected in the questionnaire.

- [ ] **Step 4: Run the targeted session test**

Run: `python -m pytest tests/test_session.py::test_installer_session_serializes_runtime_payload_fields -v`
Expected: PASS

- [ ] **Step 5: Run the full session test file**

Run: `python -m pytest tests/test_session.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_ai_control_center_installer/session.py tests/test_session.py
git commit -m "feat: add runtime payload session state"
```

### Task 2: Package And Validate The Pinned Runtime Manifest

**Files:**
- Modify: `pyproject.toml`
- Create: `src/local_ai_control_center_installer/manifests/__init__.py`
- Create: `src/local_ai_control_center_installer/manifests/windows-stable-runtime.json`
- Create: `src/local_ai_control_center_installer/runtime_bootstrap.py`
- Create: `tests/test_runtime_bootstrap.py`

- [ ] **Step 1: Write the failing manifest loading tests**

```python
import json
from pathlib import Path

import pytest

from local_ai_control_center_installer.runtime_bootstrap import (
    load_runtime_manifest,
    resolve_requested_starter_model,
)


def test_load_runtime_manifest_reads_pinned_runtime_contract(tmp_path: Path):
    manifest_path = tmp_path / "windows-stable-runtime.json"
    manifest_path.write_text(
        json.dumps(
            {
                "runtime_artifact": {
                    "id": "windows-llama-cpp-runtime",
                    "url": "https://example.invalid/runtime.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["llama-server.exe"],
                    "install_subdir": "runtime/llama.cpp",
                },
                "starter_models": {
                    "recommended-6gb": {
                        "id": "recommended-6gb",
                        "url": "https://example.invalid/model.gguf",
                        "sha256": "def456",
                        "target_filename": "recommended-6gb.gguf",
                        "install_subdir": "models/recommended-6gb",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    manifest = load_runtime_manifest(manifest_path)

    assert manifest["runtime_artifact"]["id"] == "windows-llama-cpp-runtime"
    assert manifest["starter_models"]["recommended-6gb"]["target_filename"] == "recommended-6gb.gguf"


def test_resolve_requested_starter_model_fails_for_missing_manifest_entry():
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {},
    }

    with pytest.raises(ValueError, match="starter model"):
        resolve_requested_starter_model(manifest, "recommended-24gb")


def test_load_runtime_manifest_uses_packaged_resource_by_default():
    manifest = load_runtime_manifest()

    assert "runtime_artifact" in manifest
    assert "starter_models" in manifest
    assert manifest["runtime_artifact"]["id"] == "windows-llama-cpp-runtime"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runtime_bootstrap.py::test_load_runtime_manifest_reads_pinned_runtime_contract tests/test_runtime_bootstrap.py::test_resolve_requested_starter_model_fails_for_missing_manifest_entry -v`
Expected: FAIL with `ImportError` because `runtime_bootstrap.py` does not exist yet

- [ ] **Step 3: Package manifest JSON with setuptools**

Update `pyproject.toml` with:

```toml
[tool.setuptools.package-data]
local_ai_control_center_installer = ["manifests/*.json"]
```

Create `src/local_ai_control_center_installer/manifests/__init__.py` as an empty package marker.

- [ ] **Step 4: Write the production manifest JSON**

Create `src/local_ai_control_center_installer/manifests/windows-stable-runtime.json` with this exact shape:

```json
{
  "runtime_artifact": {
    "id": "windows-llama-cpp-runtime",
    "url": "<PINNED_OFFICIAL_RUNTIME_URL>",
    "sha256": "<PINNED_OFFICIAL_RUNTIME_SHA256>",
    "archive_type": "zip",
    "required_files": [
      "llama-server.exe"
    ],
    "install_subdir": "runtime/llama.cpp"
  },
  "starter_models": {
    "recommended-6gb": {
      "id": "recommended-6gb",
      "url": "<PINNED_OFFICIAL_MODEL_URL>",
      "sha256": "<PINNED_OFFICIAL_MODEL_SHA256>",
      "target_filename": "recommended-6gb.gguf",
      "install_subdir": "models/recommended-6gb"
    }
  }
}
```

Replace the placeholder values with verified official upstream values during implementation. Do not leave the angle-bracket tokens in the committed file.

- [ ] **Step 5: Implement minimal manifest helpers**

In `runtime_bootstrap.py`, start with:

```python
import json
from importlib.resources import files


def load_runtime_manifest(manifest_path=None) -> dict:
    if manifest_path is None:
        manifest_path = files("local_ai_control_center_installer.manifests").joinpath(
            "windows-stable-runtime.json"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "runtime_artifact" not in payload or "starter_models" not in payload:
        raise ValueError("Runtime manifest is missing required top-level fields.")
    runtime_artifact = payload["runtime_artifact"]
    for key in ("id", "url", "sha256", "archive_type", "required_files", "install_subdir"):
        if key not in runtime_artifact:
            raise ValueError(f"Runtime artifact entry is missing required field: {key}")
    return payload


def resolve_requested_starter_model(manifest: dict, requested_model_id: str) -> dict:
    try:
        return manifest["starter_models"][requested_model_id]
    except KeyError as exc:
        raise ValueError(f"Missing starter model entry for {requested_model_id}") from exc
```

- [ ] **Step 6: Run the targeted manifest tests**

Run: `python -m pytest tests/test_runtime_bootstrap.py::test_load_runtime_manifest_reads_pinned_runtime_contract tests/test_runtime_bootstrap.py::test_resolve_requested_starter_model_fails_for_missing_manifest_entry -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/local_ai_control_center_installer/manifests/__init__.py src/local_ai_control_center_installer/manifests/windows-stable-runtime.json src/local_ai_control_center_installer/runtime_bootstrap.py tests/test_runtime_bootstrap.py
git commit -m "feat: add pinned runtime manifest contract"
```

### Task 3: Build Download, Verification, Metadata, And Promote Helpers

**Files:**
- Create: `src/local_ai_control_center_installer/downloads.py`
- Create: `tests/test_downloads.py`

- [ ] **Step 1: Write the failing download-helper tests**

```python
import json
from pathlib import Path

import pytest

from local_ai_control_center_installer.downloads import (
    verify_sha256,
    verify_required_files,
    write_runtime_metadata,
    verify_runtime_metadata,
)


def test_verify_sha256_accepts_matching_digest(tmp_path: Path):
    artifact_path = tmp_path / "runtime.zip"
    artifact_path.write_bytes(b"runtime-payload")

    assert verify_sha256(
        artifact_path,
        "4418f0f4a0d46f8b595f013a6d7d7926d95a79e8f7f1c2d18a0f77f8f3d3bc2c",
    ) is True


def test_verify_required_files_returns_false_when_expected_file_is_missing(tmp_path: Path):
    install_root = tmp_path / "llama.cpp"
    install_root.mkdir()
    (install_root / "llama-server.exe").write_text("ok", encoding="utf-8")

    assert verify_required_files(
        install_root,
        ["llama-server.exe", "ggml-base.dll"],
    ) is False


def test_runtime_metadata_marker_round_trip(tmp_path: Path):
    metadata_path = tmp_path / "runtime-artifact.json"
    write_runtime_metadata(
        metadata_path,
        artifact_id="windows-llama-cpp-runtime",
        source_sha256="abc123",
    )

    assert verify_runtime_metadata(
        metadata_path,
        artifact_id="windows-llama-cpp-runtime",
        source_sha256="abc123",
    ) is True


def test_extract_archive_raises_for_unsupported_archive_type(tmp_path: Path):
    archive_path = tmp_path / "runtime.tar"
    archive_path.write_bytes(b"not-a-zip")

    with pytest.raises(ValueError, match="Unsupported archive type"):
        extract_archive(archive_path, tmp_path / "output", archive_type="tar")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_downloads.py -v`
Expected: FAIL with `ImportError` because `downloads.py` does not exist yet

- [ ] **Step 3: Implement the minimal helper set**

Start `downloads.py` with:

```python
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import zipfile


def verify_sha256(path: Path, expected_sha256: str) -> bool:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == expected_sha256.lower()


def verify_required_files(root: Path, required_files: list[str]) -> bool:
    return all((root / relative_path).exists() for relative_path in required_files)


def write_runtime_metadata(metadata_path: Path, *, artifact_id: str, source_sha256: str) -> Path:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {"artifact_id": artifact_id, "source_sha256": source_sha256},
            indent=2,
        ),
        encoding="utf-8",
    )
    return metadata_path


def verify_runtime_metadata(
    metadata_path: Path,
    *,
    artifact_id: str,
    source_sha256: str,
) -> bool:
    if not metadata_path.exists():
        return False
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    return (
        payload.get("artifact_id") == artifact_id
        and payload.get("source_sha256") == source_sha256
    )


def extract_archive(archive_path: Path, destination_root: Path, *, archive_type: str) -> Path:
    if archive_type != "zip":
        raise ValueError(f"Unsupported archive type: {archive_type}")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination_root)
    return destination_root
```

- [ ] **Step 4: Add the failing promote rollback test**

Extend `tests/test_downloads.py` with:

```python
from local_ai_control_center_installer.downloads import promote_tree


def test_promote_tree_restores_preexisting_file_when_second_replace_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    staging_root = tmp_path / "staging"
    final_root = tmp_path / "final"
    (staging_root / "logs").mkdir(parents=True)
    (staging_root / "config").mkdir(parents=True)
    (staging_root / "logs" / "install.log").write_text("new", encoding="utf-8")
    (staging_root / "config" / "runtime-artifact.json").write_text("new", encoding="utf-8")
    (final_root / "logs").mkdir(parents=True)
    (final_root / "logs" / "install.log").write_text("old", encoding="utf-8")

    original_replace = Path.replace

    def fail_on_second_promote(self: Path, target: Path) -> Path:
        if target == final_root / "config" / "runtime-artifact.json":
            raise OSError("replace failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_on_second_promote)

    with pytest.raises(OSError):
        promote_tree(staging_root, final_root)

    assert (final_root / "logs" / "install.log").read_text(encoding="utf-8") == "old"
```

- [ ] **Step 5: Run the rollback test to verify it fails**

Run: `python -m pytest tests/test_downloads.py::test_promote_tree_restores_preexisting_file_when_second_replace_fails -v`
Expected: FAIL because `promote_tree` does not exist yet

- [ ] **Step 6: Implement tree promotion with rollback**

Add a slice-specific promote helper modeled after the proven bootstrap persistence approach:

```python
def promote_tree(staging_root: Path, final_root: Path) -> None:
    ...
```

Required behavior:

- promote staged files into the final tree
- back up preexisting targets before replacement
- restore preexisting targets if any later replacement fails
- remove newly created empty directories during rollback

- [ ] **Step 7: Run the full downloads test file**

Run: `python -m pytest tests/test_downloads.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/local_ai_control_center_installer/downloads.py tests/test_downloads.py
git commit -m "feat: add runtime payload download helpers"
```

### Task 4: Implement The Runtime Payload Happy Path

**Files:**
- Modify: `src/local_ai_control_center_installer/runtime_bootstrap.py`
- Modify: `tests/test_runtime_bootstrap.py`

- [ ] **Step 1: Write the failing skip and success-path orchestration tests**

```python
import json
from pathlib import Path

from local_ai_control_center_installer.runtime_bootstrap import apply_runtime_payload
from local_ai_control_center_installer.session import InstallerSession


def test_apply_runtime_payload_skips_when_bootstrap_failed(tmp_path: Path):
    session = InstallerSession(
        bootstrap_status="failed",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-6gb",
    )

    updated = apply_runtime_payload(session, temp_root=tmp_path / "temp-runs")

    assert updated.runtime_payload_status == "skipped"
    assert updated.runtime_artifact_status == "skipped"
    assert updated.starter_model_status == "skipped"
    assert updated.active_model_config_status == "skipped"


def test_apply_runtime_payload_marks_ready_when_runtime_and_model_are_verified_in_place(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    model_root = install_root / "models" / "recommended-6gb"
    metadata_path = runtime_root / "runtime-artifact.json"
    runtime_root.mkdir(parents=True)
    model_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    (model_root / "recommended-6gb.gguf").write_text("ok", encoding="utf-8")
    metadata_path.write_text(
        json.dumps({"artifact_id": "windows-llama-cpp-runtime", "source_sha256": "abc123"}),
        encoding="utf-8",
    )
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        verify_model_file=lambda path, expected_sha256: True,
    )

    assert updated.runtime_payload_status == "ready"
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "ready"
    assert updated.active_model_config_status == "ready"
    assert Path(updated.active_model_config_path).exists()


def test_apply_runtime_payload_downloads_extracts_and_promotes_runtime_payload_when_missing(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "runtime-sha",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "model-sha",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
            }
        },
    }

    def fake_download_runtime_archive(url: str, destination: Path) -> Path:
        destination.write_bytes(b"runtime-archive")
        return destination

    def fake_extract_archive(archive_path: Path, destination_root: Path, *, archive_type: str) -> Path:
        destination_root.mkdir(parents=True, exist_ok=True)
        (destination_root / "llama-server.exe").write_text("ok", encoding="utf-8")
        return destination_root

    def fake_download_model_file(url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("model", encoding="utf-8")
        return destination

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_runtime_archive=fake_download_runtime_archive,
        download_model_file=fake_download_model_file,
        extract_archive=fake_extract_archive,
        verify_archive_sha256=lambda path, expected: True,
        verify_model_file=lambda path, expected: True,
    )

    assert updated.runtime_payload_status == "ready"
    assert Path(updated.runtime_artifact_path, "llama-server.exe").exists()
    assert Path(updated.runtime_metadata_path).exists()
    assert Path(updated.starter_model_path).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runtime_bootstrap.py::test_apply_runtime_payload_skips_when_bootstrap_failed tests/test_runtime_bootstrap.py::test_apply_runtime_payload_marks_ready_when_runtime_and_model_are_verified_in_place tests/test_runtime_bootstrap.py::test_apply_runtime_payload_downloads_extracts_and_promotes_runtime_payload_when_missing -v`
Expected: FAIL because `apply_runtime_payload` does not exist yet

- [ ] **Step 3: Implement the minimal orchestration skeleton**

In `runtime_bootstrap.py`, add:

```python
from copy import deepcopy
import json
from pathlib import Path

from local_ai_control_center_installer.downloads import (
    verify_required_files,
    verify_runtime_metadata,
)


def apply_runtime_payload(
    session,
    *,
    temp_root: Path,
    load_manifest=load_runtime_manifest,
    verify_model_file=None,
):
    if session.bootstrap_status != "ready":
        session.runtime_payload_status = "skipped"
        session.runtime_artifact_status = "skipped"
        session.starter_model_status = "skipped"
        session.active_model_config_status = "skipped"
        return session
    ...
```

Implement the happy-path minimum:

- normalize `install_root`
- load manifest
- resolve requested starter model from `session.starter_model`
- verify runtime artifact in place using required file layout + metadata marker
- when runtime artifact is missing or stale:
  - download the pinned archive into temp staging
  - verify archive checksum
  - extract the archive into staged runtime content
  - verify required file layout
  - write runtime metadata marker
  - promote the staged runtime tree into the final install root
- verify starter model in place using filename + injected `verify_model_file`
- when the starter model is missing or stale:
  - download the model into temp staging
  - verify checksum
  - promote it into the final model location
- write `<install_root>/config/active-model.json`
- persist:
  - `runtime_artifact_id`
  - `runtime_artifact_path`
  - `starter_model_path`
  - `active_model_config_path`
  - `runtime_metadata_path`

- [ ] **Step 4: Run the targeted skip/success tests**

Run: `python -m pytest tests/test_runtime_bootstrap.py::test_apply_runtime_payload_skips_when_bootstrap_failed tests/test_runtime_bootstrap.py::test_apply_runtime_payload_marks_ready_when_runtime_and_model_are_verified_in_place tests/test_runtime_bootstrap.py::test_apply_runtime_payload_downloads_extracts_and_promotes_runtime_payload_when_missing -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/runtime_bootstrap.py tests/test_runtime_bootstrap.py
git commit -m "feat: add runtime payload happy path"
```

### Task 5: Add The Runtime Failure Matrix

**Files:**
- Modify: `src/local_ai_control_center_installer/runtime_bootstrap.py`
- Modify: `tests/test_runtime_bootstrap.py`

- [ ] **Step 1: Write the failing failure-path tests**

```python
def test_apply_runtime_payload_fails_when_requested_model_manifest_entry_is_missing(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-24gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {},
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "skipped"
    assert updated.starter_model_status == "failed"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "runtime-manifest"


def test_apply_runtime_payload_marks_runtime_artifact_failure_and_skips_later_steps(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-6gb",
    )
    manifest = {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "abc123",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-6gb": {
                "id": "recommended-6gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "def456",
                "target_filename": "recommended-6gb.gguf",
                "install_subdir": "models/recommended-6gb",
            }
        },
    }

    updated = apply_runtime_payload(
        session,
        temp_root=tmp_path / "temp-runs",
        load_manifest=lambda: manifest,
        download_runtime_archive=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("download failed")),
    )

    assert updated.runtime_payload_status == "failed"
    assert updated.runtime_artifact_status == "failed"
    assert updated.starter_model_status == "skipped"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "runtime-artifact"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runtime_bootstrap.py::test_apply_runtime_payload_fails_when_requested_model_manifest_entry_is_missing tests/test_runtime_bootstrap.py::test_apply_runtime_payload_marks_runtime_artifact_failure_and_skips_later_steps -v`
Expected: FAIL because the failure statuses are not implemented yet

- [ ] **Step 3: Implement manifest and runtime artifact failure handling**

Add explicit failure mapping in `apply_runtime_payload`:

- manifest failure:
  - `runtime_payload_status = failed`
  - `starter_model_status = failed` when the requested starter model entry is unavailable
  - `failing_step = "runtime-manifest"`
- runtime artifact failure:
  - `runtime_artifact_status = failed`
  - downstream runtime statuses = `skipped`
  - `failing_step = "runtime-artifact"`

- [ ] **Step 4: Add the failing model/config truth tests**

Extend `tests/test_runtime_bootstrap.py` with:

```python
def test_apply_runtime_payload_marks_model_failure_after_runtime_is_ready(...):
    ...
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "failed"
    assert updated.active_model_config_status == "skipped"
    assert updated.failing_step == "starter-model"


def test_apply_runtime_payload_marks_active_model_config_failure(...):
    ...
    assert updated.runtime_artifact_status == "ready"
    assert updated.starter_model_status == "ready"
    assert updated.active_model_config_status == "failed"
    assert updated.failing_step == "active-model-config"
```

- [ ] **Step 5: Run the new failure tests to verify they fail**

Run: `python -m pytest tests/test_runtime_bootstrap.py -k "runtime_payload_marks_" -v`
Expected: FAIL because the model/config truth table is not complete yet

- [ ] **Step 6: Implement the remaining failure matrix**

Complete `apply_runtime_payload` with:

- model download / checksum / promotion failure mapping to `starter-model`
- active model config write failure mapping to `active-model-config`
- `last_successful_step` updates when useful

- [ ] **Step 7: Run the full runtime bootstrap test file**

Run: `python -m pytest tests/test_runtime_bootstrap.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/local_ai_control_center_installer/runtime_bootstrap.py tests/test_runtime_bootstrap.py
git commit -m "feat: add runtime payload failure rules"
```

### Task 6: Extend Reporting And Wire The Runtime Phase End-To-End

**Files:**
- Modify: `src/local_ai_control_center_installer/reporting.py`
- Modify: `src/local_ai_control_center_installer/defaults.py`
- Modify: `src/local_ai_control_center_installer/main.py`
- Modify: `tests/test_reporting.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_package_smoke.py`

- [ ] **Step 1: Write the failing reporting test for runtime payload fields**

```python
def test_write_json_report_serializes_runtime_payload_summary(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    session = InstallerSession(
        bootstrap_status="ready",
        runtime_payload_status="failed",
        runtime_artifact_status="ready",
        starter_model="recommended-6gb",
        starter_model_status="failed",
        active_model_config_status="skipped",
        runtime_artifact_id="windows-llama-cpp-runtime",
        install_root=str(tmp_path / "install-root"),
        failing_step="starter-model",
    )

    write_json_report(session, paths.json_report_path)

    payload = json.loads(paths.json_report_path.read_text(encoding="utf-8"))
    assert payload["runtime_payload_status"] == "failed"
    assert payload["runtime_artifact_status"] == "ready"
    assert payload["starter_model_status"] == "failed"
    assert payload["runtime_artifact_id"] == "windows-llama-cpp-runtime"


def test_write_human_log_includes_runtime_payload_lines(tmp_path: Path):
    paths = build_run_paths(tmp_path, "2026-05-21T10-00-00")
    session = InstallerSession(
        install_root=str(tmp_path / "install-root"),
        runtime_payload_status="failed",
        runtime_artifact_status="ready",
        starter_model="recommended-6gb",
        starter_model_status="failed",
        active_model_config_status="skipped",
        runtime_artifact_id="windows-llama-cpp-runtime",
        failing_step="starter-model",
    )

    write_human_log(session, paths.log_path)

    contents = paths.log_path.read_text(encoding="utf-8")
    assert "Runtime payload status: failed" in contents
    assert "Runtime artifact status: ready" in contents
    assert "Starter model status: failed" in contents
    assert "Pinned runtime artifact id: windows-llama-cpp-runtime" in contents


def test_persist_install_root_reports_rewrites_runtime_truth_after_bootstrap_phase(tmp_path: Path):
    install_root = tmp_path / "install-root"
    session = InstallerSession(
        install_root=str(install_root),
        bootstrap_status="ready",
        runtime_payload_status="ready",
        runtime_artifact_status="ready",
        starter_model="recommended-6gb",
        starter_model_status="ready",
        active_model_config_status="ready",
    )

    persist_install_root_reports(session)

    report_payload = json.loads(
        (install_root / "logs" / "install-report.json").read_text(encoding="utf-8")
    )
    snapshot_payload = json.loads(
        (install_root / "config" / "installer-session.json").read_text(encoding="utf-8")
    )

    assert report_payload["runtime_payload_status"] == "ready"
    assert snapshot_payload["runtime_payload_status"] == "ready"
```

- [ ] **Step 2: Run the targeted reporting test to verify it fails**

Run: `python -m pytest tests/test_reporting.py::test_write_json_report_serializes_runtime_payload_summary tests/test_reporting.py::test_write_human_log_includes_runtime_payload_lines tests/test_reporting.py::test_persist_install_root_reports_rewrites_runtime_truth_after_bootstrap_phase -v`
Expected: FAIL because runtime payload fields are not yet included in the report

- [ ] **Step 3: Extend human log and JSON report writers**

Update `reporting.py` so `write_human_log()` includes lines for:

- `Runtime payload status`
- `Runtime artifact status`
- `Starter model status`
- `Active model config status`
- `Pinned runtime artifact id`
- `Selected starter model`

Update `write_json_report()` so it includes:

- `runtime_payload_status`
- `runtime_artifact_status`
- `starter_model_status`
- `active_model_config_status`
- `runtime_artifact_id`
- `starter_model`
- `runtime_artifact_path`
- `starter_model_path`
- `active_model_config_path`
- `runtime_metadata_path`

Add a new helper in `reporting.py`:

```python
def persist_install_root_reports(session: InstallerSession) -> None:
    ...
```

Required behavior:

- require a non-empty `install_root`
- rewrite:
  - `<install_root>/logs/install.log`
  - `<install_root>/logs/install-report.json`
  - `<install_root>/config/installer-session.json`
- use the same safe staging/promote pattern already proven in bootstrap persistence so runtime truth replaces bootstrap-only truth without partial writes

- [ ] **Step 4: Run the reporting test file**

Run: `python -m pytest tests/test_reporting.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing orchestration and CLI tests**

Add to `tests/test_main.py`:

```python
def test_run_installer_runs_runtime_payload_after_bootstrap_phase():
    events: list[str] = []

    def fake_apply_bootstrap(session):
        events.append("bootstrap")
        session.bootstrap_status = "ready"
        return session

    def fake_apply_runtime(session):
        events.append("runtime")
        session.runtime_payload_status = "ready"
        return session

    run_installer(
        collect_answers=lambda session: session,
        scan_dependencies=lambda session: session,
        apply_phase=fake_apply_bootstrap,
        apply_runtime_payload=fake_apply_runtime,
        write_reports=lambda session: events.append("report"),
    )

    assert events == ["bootstrap", "runtime", "report"]


def test_main_returns_non_zero_when_runtime_payload_status_is_failed(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        main_module,
        "run_installer",
        lambda: {"bootstrap_status": "ready", "runtime_payload_status": "failed"},
    )

    assert main_module.main() == 1


def test_run_installer_uses_real_default_runtime_wiring_with_stubbed_runtime_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    def fake_collect_installer_answers(session: InstallerSession):
        session.install_root = str(tmp_path / "install-root")
        session.starter_model = "recommended-6gb"
        return session

    monkeypatch.setattr(defaults_module, "collect_installer_answers", fake_collect_installer_answers)
    monkeypatch.setattr(defaults_module, "_default_temp_root", lambda: tmp_path / "temp-runs")
    monkeypatch.setattr(
        defaults_module,
        "default_apply_runtime_payload",
        lambda session: _mark_runtime_ready(session, tmp_path),
    )
    ...
```

Add a small helper in the test module if needed:

```python
def _mark_runtime_ready(session: InstallerSession, tmp_path: Path) -> InstallerSession:
    session.runtime_payload_status = "ready"
    session.runtime_artifact_status = "ready"
    session.starter_model_status = "ready"
    session.active_model_config_status = "ready"
    session.runtime_artifact_id = "windows-llama-cpp-runtime"
    session.runtime_artifact_path = str(tmp_path / "install-root" / "runtime" / "llama.cpp")
    session.starter_model_path = str(tmp_path / "install-root" / "models" / "recommended-6gb" / "recommended-6gb.gguf")
    session.active_model_config_path = str(tmp_path / "install-root" / "config" / "active-model.json")
    session.runtime_metadata_path = str(tmp_path / "install-root" / "runtime" / "llama.cpp" / "runtime-artifact.json")
    return session
```

- [ ] **Step 6: Run the targeted main tests to verify they fail**

Run: `python -m pytest tests/test_main.py::test_run_installer_runs_runtime_payload_after_bootstrap_phase tests/test_main.py::test_main_returns_non_zero_when_runtime_payload_status_is_failed -v`
Expected: FAIL because `run_installer` does not yet call a runtime step and `main()` does not yet consider runtime payload failure

- [ ] **Step 7: Wire defaults and main**

In `defaults.py`, add:

```python
from local_ai_control_center_installer.runtime_bootstrap import apply_runtime_payload


def default_apply_runtime_payload(session: InstallerSession) -> InstallerSession:
    return apply_runtime_payload(session, temp_root=_default_temp_root())
```

In `main.py`, update `run_installer()` to accept and call a runtime collaborator:

```python
def run_installer(
    *,
    collect_answers: SessionStep | None = None,
    scan_dependencies: SessionStep | None = None,
    apply_phase: SessionStep | None = None,
    apply_runtime_payload: SessionStep | None = None,
    write_reports: ReportStep | None = None,
):
    ...
    session = apply_phase(session)
    session = apply_runtime_payload(session)
    write_reports(session)
```

Then update `main()` so success requires:

- `bootstrap_status == "ready"`
- `runtime_payload_status == "ready"`

Update `default_write_reports()` so it:

- always writes temp-run human log and JSON report
- rewrites final install-root log/report/session snapshot when `session.bootstrap_status == "ready"`

- [ ] **Step 8: Update the injected smoke test**

Modify `tests/test_package_smoke.py` to pass a no-op runtime collaborator:

```python
result = run_installer(
    collect_answers=lambda session: session,
    scan_dependencies=lambda session: session,
    apply_phase=lambda session: session,
    apply_runtime_payload=lambda session: session,
    write_reports=lambda session: None,
)
```

- [ ] **Step 9: Run the main and smoke tests**

Run: `python -m pytest tests/test_main.py tests/test_package_smoke.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add src/local_ai_control_center_installer/reporting.py src/local_ai_control_center_installer/defaults.py src/local_ai_control_center_installer/main.py tests/test_reporting.py tests/test_main.py tests/test_package_smoke.py
git commit -m "feat: wire runtime payload reporting and orchestration"
```

### Task 7: Update README Slice Status And Run Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the status note in README**

Replace the bootstrap-only status language with a runtime-payload-aware status note.

State clearly that the repository now delivers:

- numbered installer questionnaire contract
- dependency bootstrap and blocking/failure classification
- pinned runtime payload preparation for `llama.cpp`
- starter model preparation
- active model configuration
- human-readable logging and JSON reporting

State clearly that the repository still does not deliver:

- runnable server verification
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
git commit -m "docs: clarify runtime payload slice scope"
```

## Done Criteria

The slice is complete only when all of the following are true:

- the installer package includes a pinned Windows runtime manifest file
- runtime manifest load failures are reported truthfully with `runtime-manifest` failure semantics
- the installer can verify an already-present `llama.cpp` payload using required-file layout plus runtime metadata marker
- the installer can verify or stage/promote the selected starter model using pinned manifest metadata
- runtime promotion failures do not leave partial final-location state behind
- final install-root log/report/session artifacts reflect runtime truth, not stale bootstrap-only truth
- `active-model.json` is written only after runtime artifact and starter model are both ready
- runtime truth is exposed through:
  - `runtime_payload_status`
  - `runtime_artifact_status`
  - `starter_model_status`
  - `active_model_config_status`
- `product_installation_status` remains `incomplete`
- `main()` exits `0` only when bootstrap and runtime payload are both ready
- all tests pass with `python -m pytest -v`

## References

- Spec: `docs/superpowers/specs/2026-05-21-windows-stable-runtime-payload-design.md`
- Previous implementation plan: `docs/superpowers/plans/2026-05-20-windows-stable-core-bootstrap.md`
- Product requirements: `docs/requirements/PRODUCT_REQUIREMENTS.md`
