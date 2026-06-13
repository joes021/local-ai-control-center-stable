# SearxNG Search Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one shared SearxNG search layer for the local model path and OpenCode `local-lacc` path without breaking the existing Windows truth model.

**Architecture:** Store shared web-search settings in the existing settings contract. Add a backend search service plus a local runtime proxy. The panel gets a dedicated `Search` tab while OpenCode gets search through the same local proxy path.

**Tech Stack:** FastAPI, standard-library HTTP calls, Vite/React, pytest, packaged frontend_dist, Windows installer build.

---

### Task 1: Lock search product contract in shared settings and docs

**Files:**
- Create: `docs/superpowers/specs/2026-05-25-searxng-search-integration-design.md`
- Create: `docs/superpowers/plans/2026-05-25-searxng-search-integration.md`
- Modify: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/settings_service.py`
- Modify: `frontend/src/lib/types.ts`
- Test: `tests/test_control_center_settings.py`

- [ ] Add failing tests for shared web-search settings defaults and normalization
- [ ] Extend backend settings contract with search mode, provider, base URL, result limit, timeout, and prefix
- [ ] Extend frontend types to reflect the new settings truth
- [ ] Run focused tests

### Task 2: Add backend SearxNG service and Search API routes

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/services/search_service.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/search.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Test: `tests/test_control_center_search_service.py`
- Create: `tests/test_control_center_search_routes.py`

- [ ] Add failing tests for SearxNG result normalization, on-demand trigger logic, and answer orchestration
- [ ] Implement shared search service with deterministic mode handling and snippet normalization
- [ ] Expose search query and search-answer routes
- [ ] Run focused tests

### Task 3: Add shared local runtime proxy for OpenCode local-lacc path

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/runtime_proxy.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Modify: `src/local_ai_control_center_installer/opencode_bootstrap.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/models_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/repair_service.py`
- Test: `tests/test_control_center_runtime_proxy.py`
- Modify: `tests/test_opencode_bootstrap.py`
- Modify: `tests/test_control_center_models_service.py`

- [ ] Add failing tests for proxy passthrough and search augmentation in `off`, `on-demand`, and `always` modes
- [ ] Point `local-lacc` managed config to the control-center proxy instead of direct runtime base URL
- [ ] Keep cloud `opencode` provider support untouched while wiring local-lacc through the proxy
- [ ] Run focused tests

### Task 4: Add visible Search tab and search settings UI

**Files:**
- Create: `frontend/src/pages/SearchPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] Add Search tab UI for query, results, and "answer with local model"
- [ ] Add shared search settings controls and honest OpenCode/local-lacc guidance
- [ ] Keep UX explicit that cloud OpenCode provider does not go through this local search layer
- [ ] Build frontend and refresh packaged frontend_dist

### Task 5: Close Windows delivery and local validation

**Files:**
- Create: `docs/release-validation/2026-05-25-windows-search-integration-validation.md`
- Modify: `README.md`
- Modify: `pyproject.toml`

- [ ] Run full `python -m pytest -q`
- [ ] Run `python -m build`
- [ ] Run `packaging/build_windows_installer.ps1 -PythonExe python`
- [ ] Upgrade this machine to the new installer
- [ ] Validate Search tab + OpenCode local-lacc web-search behavior
- [ ] Commit, push, and publish a new installer release


