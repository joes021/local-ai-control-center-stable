# Windows Release Candidate Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Windows product gaps so the public repository ships a test-ready release candidate before the Ubuntu x86_64 and Ubuntu arm64 ports begin.

**Architecture:** Keep the existing installer-managed truth model and control-panel shell, but harden the unfinished operational paths that still block a trustworthy Windows release candidate: updates, model/browser lifecycle edge cases, runtime/OpenCode truth, and release validation. After the Windows scope is stable and repeatably testable, split Linux work into a dedicated x86_64 port and then an arm64 parity pass.

**Tech Stack:** Python 3.11+, FastAPI backend, Vite/React TypeScript frontend, installer-managed manifests/config, pytest, PowerShell packaging, GitHub releases.

---

### Task 1: Restore the integrated Updates flow

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/pages/UpdatesPage.tsx`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/updates.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/updates_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Test: `tests/test_control_center_updates.py`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] Add failing backend tests for:
  - `/api/updates/check`
  - `/api/updates/install`
  - `/api/updates/progress`
  - truthful no-update / update-available / active-download / completed / error states
- [ ] Add failing frontend-dist assertions that `Updates` is back in the shipped navigation and references active update API calls
- [ ] Implement a bounded GitHub-release-backed update service that:
  - reads the latest release
  - compares against installed version
  - downloads the installer into an installer-managed update location
  - tracks percent, speed, ETA, phase, and final installer launch state
- [ ] Wire the backend routes into the integrated app
- [ ] Re-enable `Updates` in the main panel navigation
- [ ] Run focused tests, then full `python -m pytest -q`
- [ ] Commit with a Windows-update-specific message

### Task 2: Harden Browser and Models lifecycle edge cases

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/models_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/browser_catalog_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/browser_sources.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/browser.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/models.py`
- Modify: `frontend/src/pages/BrowserPage.tsx`
- Modify: `frontend/src/pages/ModelsPage.tsx`
- Modify: `frontend/src/lib/types.ts`
- Test: `tests/test_control_center_model_downloads.py`
- Test: `tests/test_control_center_models_service.py`
- Test: `tests/test_control_center_browser_sources.py`

- [ ] Add regression tests for:
  - retry/cancel/resume truth where supported
  - stale progress cleanup after worker death
  - remote catalog rows that carry unusual quant naming
  - unsupported model activation paths, including MTP safety and clear messaging
- [ ] Make Browser and Models action results converge on one canonical lifecycle contract
- [ ] Ensure active model changes cannot leave runtime state ambiguous
- [ ] Re-run focused Browser/Models suites and full tests
- [ ] Commit

### Task 3: Tighten runtime and OpenCode operational truth

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/server_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/status_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/opencode_service.py`
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/pages/ServerPage.tsx`
- Test: `tests/test_control_center_server.py`
- Test: `tests/test_control_center_status.py`
- Test: `tests/test_control_center_opencode.py`

- [ ] Add regression coverage for:
  - runtime-not-ready `OpenCode` launch behavior
  - active runtime fallback truth
  - health/port/process disagreement states
  - model/runtime incompatibility explanations
- [ ] Make panel copy and action results unambiguous when app process exists but runtime is not actually ready
- [ ] Re-run focused runtime/OpenCode suites and full tests
- [ ] Commit

### Task 4: Run Windows release-candidate validation

**Files:**
- Modify: `README.md`
- Modify: `docs/requirements/PRODUCT_REQUIREMENTS.md` only if truth gaps need explicit narrowing
- Create or modify: release-validation notes under `docs/`

- [ ] Execute clean-machine-style validation from the current workstation:
  - fresh install path
  - upgrade path
  - starter-model path
  - Browser direct download path
  - local model import path
  - runtime switch path
  - `OpenCode` launch path
  - update path
- [ ] Record supported/unsupported Windows truth clearly in docs and release notes
- [ ] Rebuild frontend, installer, wheel, tarball
- [ ] Publish a new Windows release candidate only after the whole validation checklist passes

### Task 5: Prepare Ubuntu x86_64 port plan

**Files:**
- Create: `docs/superpowers/specs/YYYY-MM-DD-ubuntu-x64-installer-design.md`
- Create: `docs/superpowers/plans/YYYY-MM-DD-ubuntu-x64-installer.md`
- Modify: platform-specific manifests/config modules as needed during implementation

- [ ] Extract Windows-specific assumptions that still leak into shared code
- [ ] Define Ubuntu x86_64 installer/runtime/control-panel path on the existing truth model
- [ ] Implement the Ubuntu x86_64 slice only after Windows release-candidate validation is done

### Task 6: Prepare Ubuntu arm64 parity pass

**Files:**
- Create: `docs/superpowers/specs/YYYY-MM-DD-ubuntu-arm64-installer-design.md`
- Create: `docs/superpowers/plans/YYYY-MM-DD-ubuntu-arm64-installer.md`

- [ ] Lock explicit arm64 support boundaries, including TurboQuant availability
- [ ] Port the Ubuntu x86_64 path with arm64-specific runtime manifest and capability rules
- [ ] Validate parity only after Ubuntu x86_64 is working


