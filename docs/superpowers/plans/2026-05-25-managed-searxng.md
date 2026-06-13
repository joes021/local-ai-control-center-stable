# Managed SearxNG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the fake `127.0.0.1:8080` search default, make Search/Settings honestly show when `SearxNG` is not configured, and add a best-effort managed local `SearxNG` bootstrap path for Windows through WSL.

**Architecture:** Add a dedicated search-provider truth layer that owns provider status, legacy-default handling, and managed bootstrap metadata. Search and Settings consume that provider status instead of guessing from a raw URL string. Managed bootstrap uses a user-space WSL install so the Windows app can stand up its own `SearxNG` instance without requiring the user to install it manually.

**Tech Stack:** Python backend services + FastAPI routes, React/Vite frontend, JSON state under installer-managed config, WSL user-space bootstrap, pytest, PowerShell packaging, GitHub releases.

---

### Task 1: Add provider truth and legacy-default migration

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/services/search_provider_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/search_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/settings_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Test: `tests/test_control_center_search_provider.py`
- Test: `tests/test_control_center_search_service.py`
- Test: `tests/test_control_center_settings.py`

- [ ] Add failing tests for `not-configured`, `wrong-service`, `healthy`, and legacy `127.0.0.1:8080` behavior.
- [ ] Stop using `127.0.0.1:8080` as the default value for new installs.
- [ ] Add provider state storage for managed bootstrap metadata.
- [ ] Make manual search fail honestly with `SearxNG nije podesen` when no real provider exists.

### Task 2: Add managed WSL bootstrap

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/search_provider_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/search.py`
- Test: `tests/test_control_center_search_provider.py`
- Test: `tests/test_control_center_search_routes.py`

- [ ] Add failing tests for `bootstrap-blocked` when WSL is unavailable.
- [ ] Implement best-effort WSL bootstrap with user-space `virtualenv`, repo clone/update, `tomli` shim for Python `<3.11`, managed `settings.yml`, and local launch verification.
- [ ] Expose bootstrap and health-check routes in the search API.

### Task 3: Surface provider truth in Search and Settings

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/SearchPage.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] Add visible provider status copy: `nije podesen`, `drugi servis`, `healthy`, `bootstrap-blocked`.
- [ ] Add `Check health`, `Setup local SearxNG`, and `Open Settings` actions in Search.
- [ ] Make Settings distinguish manual base URL from managed local SearxNG.
- [ ] Disable search actions when provider is not healthy.

### Task 4: Verify product behavior end-to-end

**Files:**
- Create: `docs/release-validation/2026-05-25-windows-managed-searxng-validation.md`
- Modify: `README.md`
- Modify: `pyproject.toml`

- [ ] Run focused tests, then full `python -m pytest -q`.
- [ ] Rebuild frontend and packaged `frontend_dist`.
- [ ] Build wheel, sdist, and Windows installer.
- [ ] Upgrade this machine locally and prove the installed panel shows the new provider truth.
- [ ] Run a live managed-bootstrap smoke on this machine and confirm `Search` can query real JSON afterward.
- [ ] Commit, push, and publish a new GitHub installer release.


