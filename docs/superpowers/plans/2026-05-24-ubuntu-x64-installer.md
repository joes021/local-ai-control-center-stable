# Ubuntu x86_64 Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first Ubuntu x86_64 port of the existing installer-managed product only after the Windows release-candidate path is stable.

**Architecture:** Reuse the Windows truth model and panel contract. Introduce a Linux platform layer for launchers, paths, packaging, and process semantics instead of branching product behavior. Keep `llama.cpp`, `OpenCode`, `Models`, `Browser`, `Settings`, `Updates`, and panel status semantics aligned with Windows wherever possible.

**Tech Stack:** Python 3.11+, shell launcher, FastAPI backend, Vite/React frontend, pytest, Linux runtime manifests, packaged control-panel launcher.

---

### Task 1: Extract Windows-only assumptions into a Linux-capable platform layer

**Files:**
- Modify: `src/local_ai_control_center_installer/windows_release.py`
- Modify: `src/local_ai_control_center_installer/control_center_panel.py`
- Modify: `src/local_ai_control_center_installer/control_center_uninstall.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/updates_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/models_service.py`
- Create: `src/local_ai_control_center_installer/linux_release.py`
- Create: `src/local_ai_control_center_installer/platform_paths.py`
- Test: `tests/test_windows_release.py`
- Create: `tests/test_linux_release.py`

- [ ] Add failing tests for Linux launcher/worker dispatch without Windows-specific flags
- [ ] Extract shared launcher truth from Windows-only entrypoints
- [ ] Create Linux release helpers for shell launch and updater/download workers
- [ ] Keep Windows behavior unchanged while making Linux path possible
- [ ] Run focused tests and then full `python -m pytest -q`

### Task 2: Add Ubuntu x64 runtime and payload manifests

**Files:**
- Modify: `src/local_ai_control_center_installer/runtime_manifest.py`
- Modify: `src/local_ai_control_center_installer/runtime_bootstrap.py`
- Modify: `src/local_ai_control_center_installer/download_plan.py`
- Create: `src/local_ai_control_center_installer/manifests/ubuntu-x64-runtime.json`
- Create: `src/local_ai_control_center_installer/manifests/ubuntu-x64-opencode.json`
- Test: `tests/test_runtime_manifest.py`
- Test: `tests/test_runtime_bootstrap.py`
- Test: `tests/test_download_plan.py`

- [ ] Add failing manifest/runtime tests for Ubuntu x64 artifact selection
- [ ] Teach manifest loading and download planning to resolve Ubuntu x64 payloads
- [ ] Preserve Windows payload behavior while introducing Linux x64 variants
- [ ] Run focused tests and full tests

### Task 3: Build Ubuntu x64 installer/bootstrap path

**Files:**
- Modify: `bootstrap/install.ps1`
- Create: `bootstrap/install.sh`
- Modify: `src/local_ai_control_center_installer/main.py`
- Modify: `src/local_ai_control_center_installer/defaults.py`
- Modify: `src/local_ai_control_center_installer/prompts.py`
- Test: `tests/test_main.py`
- Test: `tests/test_defaults.py`
- Create: `tests/test_linux_bootstrap.py`

- [ ] Add failing tests for Ubuntu x64 install root defaults and shell bootstrap behavior
- [ ] Implement shell launcher plus Python-core installer path for Ubuntu x64
- [ ] Keep numbered prompts and final reporting contract identical to Windows
- [ ] Run focused tests and full tests

### Task 4: Port control-panel launch and Linux shell integration

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_runtime.py`
- Modify: `src/local_ai_control_center_installer/control_center_panel.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/system_service.py`
- Modify: `README.md`
- Test: `tests/test_control_center_panel.py`
- Test: `tests/test_control_center_runtime_deploy.py`

- [ ] Add failing tests for Linux control-panel launcher output and runtime host paths
- [ ] Implement Linux launcher files and executable-bit handling
- [ ] Keep panel URL, API contract, and managed install-root truth aligned with Windows
- [ ] Run focused tests and full tests

### Task 5: Close Ubuntu x64 operational validation

**Files:**
- Modify: `docs/release-validation/2026-05-24-windows-rc-validation.md` only if cross-platform truth needs a shared note
- Create: `docs/release-validation/YYYY-MM-DD-ubuntu-x64-validation.md`
- Modify: `README.md`

- [ ] Validate:
  - fresh install
  - upgrade
  - starter model path
  - Browser direct download path
  - local model import path
  - runtime switch path
  - `OpenCode` launch path
  - update path
- [ ] Record supported/unsupported Ubuntu x64 truth clearly
- [ ] Publish Ubuntu x64 artifact/release only after the whole checklist passes
