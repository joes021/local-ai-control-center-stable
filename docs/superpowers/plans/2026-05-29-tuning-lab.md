# Tuning Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Izgraditi prvi `Tuning Lab` koji poredi tri seta podešavanja kroz stvarni OpenCode task, meri uspeh/brzinu/diff, čuva istoriju i ume da primeni pobednički set.

**Architecture:** Novi backend domen vodi queue, aktivni run, per-slot proxy override i istoriju eksperimenata. Frontend dobija poseban tab pod `Više` sa editorom eksperimenta, tri slota, rezultat tabelom i istorijom. Izvršavanje se oslanja na postojeći `opencode --pure run --format json` i novi tuning runtime proxy put za slot-specifične sampling override vrednosti.

**Tech Stack:** FastAPI, postojeći installer-managed JSON state fajlovi, React + TypeScript, postojeći runtime proxy i OpenCode local-lacc put, pytest.

---

## File Structure

### Backend

- Create: `src/local_ai_control_center_installer/control_center_backend/routes/tuning_lab.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/runtime_proxy.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/settings_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/opencode_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/status_service.py` only if model family helper is cleaner there

### Frontend

- Create: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/styles.css`

### Tests

- Create: `tests/test_control_center_tuning_lab.py`
- Create: `tests/test_control_center_tuning_lab_routes.py`
- Modify: `tests/test_control_center_frontend_dist.py`

### Docs / Versioning

- Modify: `pyproject.toml`
- Create: `docs/release-validation/2026-05-29-tuning-lab-validation.md`

---

### Task 1: Add Tuning Lab state paths and summary payload skeleton

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py`
- Create: `tests/test_control_center_tuning_lab.py`

- [ ] **Step 1: Write the failing config and summary tests**

Add tests for:
- `tuning_lab_history_path`
- `tuning_lab_run_state_path`
- `tuning_lab_runtime_profiles_path`
- default summary payload shape

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_tuning_lab.py -q`
Expected: FAIL because config paths and service do not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- new config path properties
- `load_tuning_lab_summary()`
- default slot skeletons
- default queue/history payloads

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_tuning_lab.py -q`
Expected: PASS

---

### Task 2: Add route surface and history/run-state persistence

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/tuning_lab.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py`
- Create: `tests/test_control_center_tuning_lab_routes.py`

- [ ] **Step 1: Write failing route tests**

Cover:
- `GET /api/tuning-lab`
- `GET /api/tuning-lab/run-status`
- `GET /api/tuning-lab/history`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_tuning_lab_routes.py -q`
Expected: FAIL because routes are missing.

- [ ] **Step 3: Write minimal implementation**

Implement route wiring and simple service-backed payloads.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_tuning_lab_routes.py -q`
Expected: PASS

---

### Task 3: Add tuning runtime proxy profiles and OpenCode run execution core

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/runtime_proxy.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py`
- Modify: `tests/test_control_center_tuning_lab.py`

- [ ] **Step 1: Write failing tests for slot-specific proxy overrides**

Cover:
- tuning token resolves sampling defaults
- different tokens produce different `temperature` / `top_p` / `max_tokens`
- fallback to normal proxy path stays unchanged

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_tuning_lab.py -q`
Expected: FAIL because tuning proxy profile resolution does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- runtime proxy tuning route
- token-to-settings patch lookup
- payload overlay for chat/completions and completions

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_tuning_lab.py -q`
Expected: PASS

---

### Task 4: Add isolated workspace preparation, success checks, diff capture and winner scoring

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py`
- Modify: `tests/test_control_center_tuning_lab.py`

- [ ] **Step 1: Write failing tests for workspace mode, diff summary and winner selection**

Cover:
- git repo -> `git-worktree`
- non-git dir -> `copy`
- failed success check marks slot failed
- winner prefers successful + faster slot
- failed runs are stored in history

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_tuning_lab.py -q`
Expected: FAIL because execution core is missing.

- [ ] **Step 3: Write minimal implementation**

Implement:
- workspace preparation
- before/after snapshot diff
- success check chain
- slot result schema
- automatic winner suggestion

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_tuning_lab.py -q`
Expected: PASS

---

### Task 5: Add queue execution, apply winner, export/share and recommendation logic

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/tuning_lab.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/settings_service.py`
- Modify: `tests/test_control_center_tuning_lab.py`
- Modify: `tests/test_control_center_tuning_lab_routes.py`

- [ ] **Step 1: Write failing tests for queue, apply and export**

Cover:
- queued experiment starts when no active run exists
- second experiment stays queued
- apply winner writes settings
- export returns JSON payload
- recommended slot uses history fallback

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_tuning_lab.py tests/test_control_center_tuning_lab_routes.py -q`
Expected: FAIL because queue/apply/export are missing.

- [ ] **Step 3: Write minimal implementation**

Implement:
- sequential queue worker
- apply winner route
- export route
- recommendation rules + history lookup

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_tuning_lab.py tests/test_control_center_tuning_lab_routes.py -q`
Expected: PASS

---

### Task 6: Add frontend tab, API bindings and result UX

**Files:**
- Create: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write failing frontend-dist tests**

Cover:
- app includes `Tuning Lab`
- page source includes queue, slot table, winner apply, export/share, import snippet
- styles include tuning lab grid/table classes

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -q`
Expected: FAIL because page and strings do not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- new page under `Više`
- experiment editor
- 3 slot compare table
- queue/status
- history with pagination
- slot detail expanders
- apply/export actions

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -q`
Expected: PASS

---

### Task 7: Integrate snippet import, success-check templates and OpenCode command visibility

**Files:**
- Modify: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py`
- Modify: `tests/test_control_center_tuning_lab.py`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write failing tests for import parser and template payloads**

Cover:
- snippet parser extracts `temperature`, `top_k`, `top_p`, `min_p`, `seed`
- payload exposes success check templates
- payload exposes current runtime/model summary for baseline

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_tuning_lab.py tests/test_control_center_frontend_dist.py -q`
Expected: FAIL because parser/template integration is incomplete.

- [ ] **Step 3: Write minimal implementation**

Implement:
- custom snippet parsing
- template/autodetect payloads
- visible command/result helpers

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_tuning_lab.py tests/test_control_center_frontend_dist.py -q`
Expected: PASS

---

### Task 8: Full verification, bundle refresh, installer build and release evidence

**Files:**
- Modify: `pyproject.toml`
- Modify packaged frontend dist under `src/local_ai_control_center_installer/control_center_backend/frontend_dist/*`
- Create: `docs/release-validation/2026-05-29-tuning-lab-validation.md`

- [ ] **Step 1: Run targeted tests**

Run: `python -m pytest tests/test_control_center_tuning_lab.py tests/test_control_center_tuning_lab_routes.py tests/test_control_center_frontend_dist.py -q`
Expected: PASS

- [ ] **Step 2: Run full suite**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 3: Build package**

Run: `python -m build`
Expected: success

- [ ] **Step 4: Build Windows installer**

Run: `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`
Expected: success

- [ ] **Step 5: Capture validation evidence**

Record:
- test counts
- local app version
- live route proof
- install report status

---

## Execution Notes

- Prefer TDD cycle per backend slice before UI.
- Reuse existing helper patterns from:
  - `benchmark_service.py`
  - `jobs_service.py`
  - `opencode_service.py`
  - `first_run_validation.py`
- Keep new JSON state installer-managed and UTF-8.
- Do not touch unrelated untracked docs from `2026-05-20`.
