# Windows Final Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zavrsiti poslednji Windows stabilizacioni sprint tako da `Local AI Control Center` bude spreman za spoljasnje testiranje bez prelaska na Linux dok god Windows nije stvarno ispeglan.

**Architecture:** Zadrzati postojeci installer-managed truth model i panel, ali zatvoriti preostale produktske ivice kroz tri uska bloka: `Models + Browser` lifecycle hardening, runtime/OpenCode operational truth, pa zatim fresh-install / upgrade / update validaciju i novi Windows release.

**Tech Stack:** Python 3.11+, FastAPI backend, Vite/React TypeScript frontend, pytest, PowerShell packaging, GitHub releases.

---

### Task 1: Harden Models and Browser lifecycle truth

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/models_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/browser_catalog_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/browser_sources.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/browser.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/models.py`
- Modify: `frontend/src/pages/BrowserPage.tsx`
- Modify: `frontend/src/pages/ModelsPage.tsx`
- Test: `tests/test_control_center_model_downloads.py`
- Test: `tests/test_control_center_models_service.py`
- Test: `tests/test_control_center_browser_sources.py`

- [ ] **Step 1: Write failing regression tests for stale and regressing download state**
- [ ] **Step 2: Run focused tests and confirm the new cases fail for the expected reason**
- [ ] **Step 3: Tighten backend progress truth so dead workers, regressing snapshots, and stale progress files cannot masquerade as live downloads**
- [ ] **Step 4: Write failing regression tests for unsupported activation and Browser/Models lifecycle divergence**
- [ ] **Step 5: Make Browser and Models action results converge on one canonical lifecycle contract**
- [ ] **Step 6: Rebuild frontend if UI copy/status rendering changes**
- [ ] **Step 7: Run focused Browser/Models suites**
- [ ] **Step 8: Commit with a Browser/Models hardening message**

### Task 2: Tighten runtime and OpenCode operational truth

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

- [ ] **Step 1: Write failing regression tests for runtime-not-ready, health disagreement, and app-only OpenCode states**
- [ ] **Step 2: Run focused runtime/OpenCode tests and confirm the failures are real**
- [ ] **Step 3: Tighten runtime readiness and fallback behavior without weakening truthful status reporting**
- [ ] **Step 4: Update panel copy so running app process and usable runtime connection are clearly separated**
- [ ] **Step 5: Run focused runtime/OpenCode suites**
- [ ] **Step 6: Commit with a runtime/OpenCode truth message**

### Task 3: Run Windows release-candidate validation and ship

**Files:**
- Modify: `README.md`
- Create or modify: `docs/release-validation/2026-05-24-windows-final-polish-validation.md`
- Modify as needed: packaging/release metadata files

- [ ] **Step 1: Run fresh verification commands for tests, source build, and packaged installer build**
- [ ] **Step 2: Execute local validation checklist for fresh install, upgrade, Browser download, local import, runtime switch, OpenCode launch, and update path**
- [ ] **Step 3: Record truthful validation notes under docs/release-validation**
- [ ] **Step 4: Update README/current-scope language if validation reveals narrower truth**
- [ ] **Step 5: Build Windows installer, wheel, and sdist**
- [ ] **Step 6: Publish a new Windows release only after the validation checklist passes**
